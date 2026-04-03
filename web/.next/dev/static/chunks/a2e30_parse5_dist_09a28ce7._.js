(globalThis.TURBOPACK || (globalThis.TURBOPACK = [])).push([typeof document === "object" ? document.currentScript : undefined,
"[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/unicode.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "CODE_POINTS",
    ()=>CODE_POINTS,
    "REPLACEMENT_CHARACTER",
    ()=>REPLACEMENT_CHARACTER,
    "SEQUENCES",
    ()=>SEQUENCES,
    "getSurrogatePairCodePoint",
    ()=>getSurrogatePairCodePoint,
    "isControlCodePoint",
    ()=>isControlCodePoint,
    "isSurrogate",
    ()=>isSurrogate,
    "isSurrogatePair",
    ()=>isSurrogatePair,
    "isUndefinedCodePoint",
    ()=>isUndefinedCodePoint
]);
const UNDEFINED_CODE_POINTS = new Set([
    65534,
    65535,
    131070,
    131071,
    196606,
    196607,
    262142,
    262143,
    327678,
    327679,
    393214,
    393215,
    458750,
    458751,
    524286,
    524287,
    589822,
    589823,
    655358,
    655359,
    720894,
    720895,
    786430,
    786431,
    851966,
    851967,
    917502,
    917503,
    983038,
    983039,
    1048574,
    1048575,
    1114110,
    1114111
]);
const REPLACEMENT_CHARACTER = '\uFFFD';
var CODE_POINTS;
(function(CODE_POINTS) {
    CODE_POINTS[CODE_POINTS["EOF"] = -1] = "EOF";
    CODE_POINTS[CODE_POINTS["NULL"] = 0] = "NULL";
    CODE_POINTS[CODE_POINTS["TABULATION"] = 9] = "TABULATION";
    CODE_POINTS[CODE_POINTS["CARRIAGE_RETURN"] = 13] = "CARRIAGE_RETURN";
    CODE_POINTS[CODE_POINTS["LINE_FEED"] = 10] = "LINE_FEED";
    CODE_POINTS[CODE_POINTS["FORM_FEED"] = 12] = "FORM_FEED";
    CODE_POINTS[CODE_POINTS["SPACE"] = 32] = "SPACE";
    CODE_POINTS[CODE_POINTS["EXCLAMATION_MARK"] = 33] = "EXCLAMATION_MARK";
    CODE_POINTS[CODE_POINTS["QUOTATION_MARK"] = 34] = "QUOTATION_MARK";
    CODE_POINTS[CODE_POINTS["AMPERSAND"] = 38] = "AMPERSAND";
    CODE_POINTS[CODE_POINTS["APOSTROPHE"] = 39] = "APOSTROPHE";
    CODE_POINTS[CODE_POINTS["HYPHEN_MINUS"] = 45] = "HYPHEN_MINUS";
    CODE_POINTS[CODE_POINTS["SOLIDUS"] = 47] = "SOLIDUS";
    CODE_POINTS[CODE_POINTS["DIGIT_0"] = 48] = "DIGIT_0";
    CODE_POINTS[CODE_POINTS["DIGIT_9"] = 57] = "DIGIT_9";
    CODE_POINTS[CODE_POINTS["SEMICOLON"] = 59] = "SEMICOLON";
    CODE_POINTS[CODE_POINTS["LESS_THAN_SIGN"] = 60] = "LESS_THAN_SIGN";
    CODE_POINTS[CODE_POINTS["EQUALS_SIGN"] = 61] = "EQUALS_SIGN";
    CODE_POINTS[CODE_POINTS["GREATER_THAN_SIGN"] = 62] = "GREATER_THAN_SIGN";
    CODE_POINTS[CODE_POINTS["QUESTION_MARK"] = 63] = "QUESTION_MARK";
    CODE_POINTS[CODE_POINTS["LATIN_CAPITAL_A"] = 65] = "LATIN_CAPITAL_A";
    CODE_POINTS[CODE_POINTS["LATIN_CAPITAL_Z"] = 90] = "LATIN_CAPITAL_Z";
    CODE_POINTS[CODE_POINTS["RIGHT_SQUARE_BRACKET"] = 93] = "RIGHT_SQUARE_BRACKET";
    CODE_POINTS[CODE_POINTS["GRAVE_ACCENT"] = 96] = "GRAVE_ACCENT";
    CODE_POINTS[CODE_POINTS["LATIN_SMALL_A"] = 97] = "LATIN_SMALL_A";
    CODE_POINTS[CODE_POINTS["LATIN_SMALL_Z"] = 122] = "LATIN_SMALL_Z";
})(CODE_POINTS || (CODE_POINTS = {}));
const SEQUENCES = {
    DASH_DASH: '--',
    CDATA_START: '[CDATA[',
    DOCTYPE: 'doctype',
    SCRIPT: 'script',
    PUBLIC: 'public',
    SYSTEM: 'system'
};
function isSurrogate(cp) {
    return cp >= 55296 && cp <= 57343;
}
function isSurrogatePair(cp) {
    return cp >= 56320 && cp <= 57343;
}
function getSurrogatePairCodePoint(cp1, cp2) {
    return (cp1 - 55296) * 1024 + 9216 + cp2;
}
function isControlCodePoint(cp) {
    return cp !== 0x20 && cp !== 0x0a && cp !== 0x0d && cp !== 0x09 && cp !== 0x0c && cp >= 0x01 && cp <= 0x1f || cp >= 0x7f && cp <= 0x9f;
}
function isUndefinedCodePoint(cp) {
    return cp >= 64976 && cp <= 65007 || UNDEFINED_CODE_POINTS.has(cp);
}
}),
"[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/error-codes.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ERR",
    ()=>ERR
]);
var ERR;
(function(ERR) {
    ERR["controlCharacterInInputStream"] = "control-character-in-input-stream";
    ERR["noncharacterInInputStream"] = "noncharacter-in-input-stream";
    ERR["surrogateInInputStream"] = "surrogate-in-input-stream";
    ERR["nonVoidHtmlElementStartTagWithTrailingSolidus"] = "non-void-html-element-start-tag-with-trailing-solidus";
    ERR["endTagWithAttributes"] = "end-tag-with-attributes";
    ERR["endTagWithTrailingSolidus"] = "end-tag-with-trailing-solidus";
    ERR["unexpectedSolidusInTag"] = "unexpected-solidus-in-tag";
    ERR["unexpectedNullCharacter"] = "unexpected-null-character";
    ERR["unexpectedQuestionMarkInsteadOfTagName"] = "unexpected-question-mark-instead-of-tag-name";
    ERR["invalidFirstCharacterOfTagName"] = "invalid-first-character-of-tag-name";
    ERR["unexpectedEqualsSignBeforeAttributeName"] = "unexpected-equals-sign-before-attribute-name";
    ERR["missingEndTagName"] = "missing-end-tag-name";
    ERR["unexpectedCharacterInAttributeName"] = "unexpected-character-in-attribute-name";
    ERR["unknownNamedCharacterReference"] = "unknown-named-character-reference";
    ERR["missingSemicolonAfterCharacterReference"] = "missing-semicolon-after-character-reference";
    ERR["unexpectedCharacterAfterDoctypeSystemIdentifier"] = "unexpected-character-after-doctype-system-identifier";
    ERR["unexpectedCharacterInUnquotedAttributeValue"] = "unexpected-character-in-unquoted-attribute-value";
    ERR["eofBeforeTagName"] = "eof-before-tag-name";
    ERR["eofInTag"] = "eof-in-tag";
    ERR["missingAttributeValue"] = "missing-attribute-value";
    ERR["missingWhitespaceBetweenAttributes"] = "missing-whitespace-between-attributes";
    ERR["missingWhitespaceAfterDoctypePublicKeyword"] = "missing-whitespace-after-doctype-public-keyword";
    ERR["missingWhitespaceBetweenDoctypePublicAndSystemIdentifiers"] = "missing-whitespace-between-doctype-public-and-system-identifiers";
    ERR["missingWhitespaceAfterDoctypeSystemKeyword"] = "missing-whitespace-after-doctype-system-keyword";
    ERR["missingQuoteBeforeDoctypePublicIdentifier"] = "missing-quote-before-doctype-public-identifier";
    ERR["missingQuoteBeforeDoctypeSystemIdentifier"] = "missing-quote-before-doctype-system-identifier";
    ERR["missingDoctypePublicIdentifier"] = "missing-doctype-public-identifier";
    ERR["missingDoctypeSystemIdentifier"] = "missing-doctype-system-identifier";
    ERR["abruptDoctypePublicIdentifier"] = "abrupt-doctype-public-identifier";
    ERR["abruptDoctypeSystemIdentifier"] = "abrupt-doctype-system-identifier";
    ERR["cdataInHtmlContent"] = "cdata-in-html-content";
    ERR["incorrectlyOpenedComment"] = "incorrectly-opened-comment";
    ERR["eofInScriptHtmlCommentLikeText"] = "eof-in-script-html-comment-like-text";
    ERR["eofInDoctype"] = "eof-in-doctype";
    ERR["nestedComment"] = "nested-comment";
    ERR["abruptClosingOfEmptyComment"] = "abrupt-closing-of-empty-comment";
    ERR["eofInComment"] = "eof-in-comment";
    ERR["incorrectlyClosedComment"] = "incorrectly-closed-comment";
    ERR["eofInCdata"] = "eof-in-cdata";
    ERR["absenceOfDigitsInNumericCharacterReference"] = "absence-of-digits-in-numeric-character-reference";
    ERR["nullCharacterReference"] = "null-character-reference";
    ERR["surrogateCharacterReference"] = "surrogate-character-reference";
    ERR["characterReferenceOutsideUnicodeRange"] = "character-reference-outside-unicode-range";
    ERR["controlCharacterReference"] = "control-character-reference";
    ERR["noncharacterCharacterReference"] = "noncharacter-character-reference";
    ERR["missingWhitespaceBeforeDoctypeName"] = "missing-whitespace-before-doctype-name";
    ERR["missingDoctypeName"] = "missing-doctype-name";
    ERR["invalidCharacterSequenceAfterDoctypeName"] = "invalid-character-sequence-after-doctype-name";
    ERR["duplicateAttribute"] = "duplicate-attribute";
    ERR["nonConformingDoctype"] = "non-conforming-doctype";
    ERR["missingDoctype"] = "missing-doctype";
    ERR["misplacedDoctype"] = "misplaced-doctype";
    ERR["endTagWithoutMatchingOpenElement"] = "end-tag-without-matching-open-element";
    ERR["closingOfElementWithOpenChildElements"] = "closing-of-element-with-open-child-elements";
    ERR["disallowedContentInNoscriptInHead"] = "disallowed-content-in-noscript-in-head";
    ERR["openElementsLeftAfterEof"] = "open-elements-left-after-eof";
    ERR["abandonedHeadElementChild"] = "abandoned-head-element-child";
    ERR["misplacedStartTagForHeadElement"] = "misplaced-start-tag-for-head-element";
    ERR["nestedNoscriptInHead"] = "nested-noscript-in-head";
    ERR["eofInElementThatCanContainOnlyText"] = "eof-in-element-that-can-contain-only-text";
})(ERR || (ERR = {}));
}),
"[project]/coding/projects/LangBot/web/node_modules/parse5/dist/tokenizer/preprocessor.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Preprocessor",
    ()=>Preprocessor
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/unicode.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/error-codes.js [app-client] (ecmascript)");
;
;
//Const
const DEFAULT_BUFFER_WATERLINE = 1 << 16;
class Preprocessor {
    constructor(handler){
        this.handler = handler;
        this.html = '';
        this.pos = -1;
        // NOTE: Initial `lastGapPos` is -2, to ensure `col` on initialisation is 0
        this.lastGapPos = -2;
        this.gapStack = [];
        this.skipNextNewLine = false;
        this.lastChunkWritten = false;
        this.endOfChunkHit = false;
        this.bufferWaterline = DEFAULT_BUFFER_WATERLINE;
        this.isEol = false;
        this.lineStartPos = 0;
        this.droppedBufferSize = 0;
        this.line = 1;
        //NOTE: avoid reporting errors twice on advance/retreat
        this.lastErrOffset = -1;
    }
    /** The column on the current line. If we just saw a gap (eg. a surrogate pair), return the index before. */ get col() {
        return this.pos - this.lineStartPos + Number(this.lastGapPos !== this.pos);
    }
    get offset() {
        return this.droppedBufferSize + this.pos;
    }
    getError(code, cpOffset) {
        const { line, col, offset } = this;
        const startCol = col + cpOffset;
        const startOffset = offset + cpOffset;
        return {
            code,
            startLine: line,
            endLine: line,
            startCol,
            endCol: startCol,
            startOffset,
            endOffset: startOffset
        };
    }
    _err(code) {
        if (this.handler.onParseError && this.lastErrOffset !== this.offset) {
            this.lastErrOffset = this.offset;
            this.handler.onParseError(this.getError(code, 0));
        }
    }
    _addGap() {
        this.gapStack.push(this.lastGapPos);
        this.lastGapPos = this.pos;
    }
    _processSurrogate(cp) {
        //NOTE: try to peek a surrogate pair
        if (this.pos !== this.html.length - 1) {
            const nextCp = this.html.charCodeAt(this.pos + 1);
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isSurrogatePair"])(nextCp)) {
                //NOTE: we have a surrogate pair. Peek pair character and recalculate code point.
                this.pos++;
                //NOTE: add a gap that should be avoided during retreat
                this._addGap();
                return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSurrogatePairCodePoint"])(cp, nextCp);
            }
        } else if (!this.lastChunkWritten) {
            this.endOfChunkHit = true;
            return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF;
        }
        //NOTE: isolated surrogate
        this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].surrogateInInputStream);
        return cp;
    }
    willDropParsedChunk() {
        return this.pos > this.bufferWaterline;
    }
    dropParsedChunk() {
        if (this.willDropParsedChunk()) {
            this.html = this.html.substring(this.pos);
            this.lineStartPos -= this.pos;
            this.droppedBufferSize += this.pos;
            this.pos = 0;
            this.lastGapPos = -2;
            this.gapStack.length = 0;
        }
    }
    write(chunk, isLastChunk) {
        if (this.html.length > 0) {
            this.html += chunk;
        } else {
            this.html = chunk;
        }
        this.endOfChunkHit = false;
        this.lastChunkWritten = isLastChunk;
    }
    insertHtmlAtCurrentPos(chunk) {
        this.html = this.html.substring(0, this.pos + 1) + chunk + this.html.substring(this.pos + 1);
        this.endOfChunkHit = false;
    }
    startsWith(pattern, caseSensitive) {
        // Check if our buffer has enough characters
        if (this.pos + pattern.length > this.html.length) {
            this.endOfChunkHit = !this.lastChunkWritten;
            return false;
        }
        if (caseSensitive) {
            return this.html.startsWith(pattern, this.pos);
        }
        for(let i = 0; i < pattern.length; i++){
            const cp = this.html.charCodeAt(this.pos + i) | 0x20;
            if (cp !== pattern.charCodeAt(i)) {
                return false;
            }
        }
        return true;
    }
    peek(offset) {
        const pos = this.pos + offset;
        if (pos >= this.html.length) {
            this.endOfChunkHit = !this.lastChunkWritten;
            return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF;
        }
        const code = this.html.charCodeAt(pos);
        return code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].CARRIAGE_RETURN ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED : code;
    }
    advance() {
        this.pos++;
        //NOTE: LF should be in the last column of the line
        if (this.isEol) {
            this.isEol = false;
            this.line++;
            this.lineStartPos = this.pos;
        }
        if (this.pos >= this.html.length) {
            this.endOfChunkHit = !this.lastChunkWritten;
            return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF;
        }
        let cp = this.html.charCodeAt(this.pos);
        //NOTE: all U+000D CARRIAGE RETURN (CR) characters must be converted to U+000A LINE FEED (LF) characters
        if (cp === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].CARRIAGE_RETURN) {
            this.isEol = true;
            this.skipNextNewLine = true;
            return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED;
        }
        //NOTE: any U+000A LINE FEED (LF) characters that immediately follow a U+000D CARRIAGE RETURN (CR) character
        //must be ignored.
        if (cp === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED) {
            this.isEol = true;
            if (this.skipNextNewLine) {
                // `line` will be bumped again in the recursive call.
                this.line--;
                this.skipNextNewLine = false;
                this._addGap();
                return this.advance();
            }
        }
        this.skipNextNewLine = false;
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isSurrogate"])(cp)) {
            cp = this._processSurrogate(cp);
        }
        //OPTIMIZATION: first check if code point is in the common allowed
        //range (ASCII alphanumeric, whitespaces, big chunk of BMP)
        //before going into detailed performance cost validation.
        const isCommonValidRange = this.handler.onParseError === null || cp > 0x1f && cp < 0x7f || cp === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED || cp === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].CARRIAGE_RETURN || cp > 0x9f && cp < 64976;
        if (!isCommonValidRange) {
            this._checkForProblematicCharacters(cp);
        }
        return cp;
    }
    _checkForProblematicCharacters(cp) {
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isControlCodePoint"])(cp)) {
            this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].controlCharacterInInputStream);
        } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isUndefinedCodePoint"])(cp)) {
            this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].noncharacterInInputStream);
        }
    }
    retreat(count) {
        this.pos -= count;
        while(this.pos < this.lastGapPos){
            this.lastGapPos = this.gapStack.pop();
            this.pos--;
        }
        this.isEol = false;
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/token.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "TokenType",
    ()=>TokenType,
    "getTokenAttr",
    ()=>getTokenAttr
]);
var TokenType;
(function(TokenType) {
    TokenType[TokenType["CHARACTER"] = 0] = "CHARACTER";
    TokenType[TokenType["NULL_CHARACTER"] = 1] = "NULL_CHARACTER";
    TokenType[TokenType["WHITESPACE_CHARACTER"] = 2] = "WHITESPACE_CHARACTER";
    TokenType[TokenType["START_TAG"] = 3] = "START_TAG";
    TokenType[TokenType["END_TAG"] = 4] = "END_TAG";
    TokenType[TokenType["COMMENT"] = 5] = "COMMENT";
    TokenType[TokenType["DOCTYPE"] = 6] = "DOCTYPE";
    TokenType[TokenType["EOF"] = 7] = "EOF";
    TokenType[TokenType["HIBERNATION"] = 8] = "HIBERNATION";
})(TokenType || (TokenType = {}));
function getTokenAttr(token, attrName) {
    for(let i = token.attrs.length - 1; i >= 0; i--){
        if (token.attrs[i].name === attrName) {
            return token.attrs[i].value;
        }
    }
    return null;
}
}),
"[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/html.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/** All valid namespaces in HTML. */ __turbopack_context__.s([
    "ATTRS",
    ()=>ATTRS,
    "DOCUMENT_MODE",
    ()=>DOCUMENT_MODE,
    "NS",
    ()=>NS,
    "NUMBERED_HEADERS",
    ()=>NUMBERED_HEADERS,
    "SPECIAL_ELEMENTS",
    ()=>SPECIAL_ELEMENTS,
    "TAG_ID",
    ()=>TAG_ID,
    "TAG_NAMES",
    ()=>TAG_NAMES,
    "getTagID",
    ()=>getTagID,
    "hasUnescapedText",
    ()=>hasUnescapedText
]);
var NS;
(function(NS) {
    NS["HTML"] = "http://www.w3.org/1999/xhtml";
    NS["MATHML"] = "http://www.w3.org/1998/Math/MathML";
    NS["SVG"] = "http://www.w3.org/2000/svg";
    NS["XLINK"] = "http://www.w3.org/1999/xlink";
    NS["XML"] = "http://www.w3.org/XML/1998/namespace";
    NS["XMLNS"] = "http://www.w3.org/2000/xmlns/";
})(NS || (NS = {}));
var ATTRS;
(function(ATTRS) {
    ATTRS["TYPE"] = "type";
    ATTRS["ACTION"] = "action";
    ATTRS["ENCODING"] = "encoding";
    ATTRS["PROMPT"] = "prompt";
    ATTRS["NAME"] = "name";
    ATTRS["COLOR"] = "color";
    ATTRS["FACE"] = "face";
    ATTRS["SIZE"] = "size";
})(ATTRS || (ATTRS = {}));
var DOCUMENT_MODE;
(function(DOCUMENT_MODE) {
    DOCUMENT_MODE["NO_QUIRKS"] = "no-quirks";
    DOCUMENT_MODE["QUIRKS"] = "quirks";
    DOCUMENT_MODE["LIMITED_QUIRKS"] = "limited-quirks";
})(DOCUMENT_MODE || (DOCUMENT_MODE = {}));
var TAG_NAMES;
(function(TAG_NAMES) {
    TAG_NAMES["A"] = "a";
    TAG_NAMES["ADDRESS"] = "address";
    TAG_NAMES["ANNOTATION_XML"] = "annotation-xml";
    TAG_NAMES["APPLET"] = "applet";
    TAG_NAMES["AREA"] = "area";
    TAG_NAMES["ARTICLE"] = "article";
    TAG_NAMES["ASIDE"] = "aside";
    TAG_NAMES["B"] = "b";
    TAG_NAMES["BASE"] = "base";
    TAG_NAMES["BASEFONT"] = "basefont";
    TAG_NAMES["BGSOUND"] = "bgsound";
    TAG_NAMES["BIG"] = "big";
    TAG_NAMES["BLOCKQUOTE"] = "blockquote";
    TAG_NAMES["BODY"] = "body";
    TAG_NAMES["BR"] = "br";
    TAG_NAMES["BUTTON"] = "button";
    TAG_NAMES["CAPTION"] = "caption";
    TAG_NAMES["CENTER"] = "center";
    TAG_NAMES["CODE"] = "code";
    TAG_NAMES["COL"] = "col";
    TAG_NAMES["COLGROUP"] = "colgroup";
    TAG_NAMES["DD"] = "dd";
    TAG_NAMES["DESC"] = "desc";
    TAG_NAMES["DETAILS"] = "details";
    TAG_NAMES["DIALOG"] = "dialog";
    TAG_NAMES["DIR"] = "dir";
    TAG_NAMES["DIV"] = "div";
    TAG_NAMES["DL"] = "dl";
    TAG_NAMES["DT"] = "dt";
    TAG_NAMES["EM"] = "em";
    TAG_NAMES["EMBED"] = "embed";
    TAG_NAMES["FIELDSET"] = "fieldset";
    TAG_NAMES["FIGCAPTION"] = "figcaption";
    TAG_NAMES["FIGURE"] = "figure";
    TAG_NAMES["FONT"] = "font";
    TAG_NAMES["FOOTER"] = "footer";
    TAG_NAMES["FOREIGN_OBJECT"] = "foreignObject";
    TAG_NAMES["FORM"] = "form";
    TAG_NAMES["FRAME"] = "frame";
    TAG_NAMES["FRAMESET"] = "frameset";
    TAG_NAMES["H1"] = "h1";
    TAG_NAMES["H2"] = "h2";
    TAG_NAMES["H3"] = "h3";
    TAG_NAMES["H4"] = "h4";
    TAG_NAMES["H5"] = "h5";
    TAG_NAMES["H6"] = "h6";
    TAG_NAMES["HEAD"] = "head";
    TAG_NAMES["HEADER"] = "header";
    TAG_NAMES["HGROUP"] = "hgroup";
    TAG_NAMES["HR"] = "hr";
    TAG_NAMES["HTML"] = "html";
    TAG_NAMES["I"] = "i";
    TAG_NAMES["IMG"] = "img";
    TAG_NAMES["IMAGE"] = "image";
    TAG_NAMES["INPUT"] = "input";
    TAG_NAMES["IFRAME"] = "iframe";
    TAG_NAMES["KEYGEN"] = "keygen";
    TAG_NAMES["LABEL"] = "label";
    TAG_NAMES["LI"] = "li";
    TAG_NAMES["LINK"] = "link";
    TAG_NAMES["LISTING"] = "listing";
    TAG_NAMES["MAIN"] = "main";
    TAG_NAMES["MALIGNMARK"] = "malignmark";
    TAG_NAMES["MARQUEE"] = "marquee";
    TAG_NAMES["MATH"] = "math";
    TAG_NAMES["MENU"] = "menu";
    TAG_NAMES["META"] = "meta";
    TAG_NAMES["MGLYPH"] = "mglyph";
    TAG_NAMES["MI"] = "mi";
    TAG_NAMES["MO"] = "mo";
    TAG_NAMES["MN"] = "mn";
    TAG_NAMES["MS"] = "ms";
    TAG_NAMES["MTEXT"] = "mtext";
    TAG_NAMES["NAV"] = "nav";
    TAG_NAMES["NOBR"] = "nobr";
    TAG_NAMES["NOFRAMES"] = "noframes";
    TAG_NAMES["NOEMBED"] = "noembed";
    TAG_NAMES["NOSCRIPT"] = "noscript";
    TAG_NAMES["OBJECT"] = "object";
    TAG_NAMES["OL"] = "ol";
    TAG_NAMES["OPTGROUP"] = "optgroup";
    TAG_NAMES["OPTION"] = "option";
    TAG_NAMES["P"] = "p";
    TAG_NAMES["PARAM"] = "param";
    TAG_NAMES["PLAINTEXT"] = "plaintext";
    TAG_NAMES["PRE"] = "pre";
    TAG_NAMES["RB"] = "rb";
    TAG_NAMES["RP"] = "rp";
    TAG_NAMES["RT"] = "rt";
    TAG_NAMES["RTC"] = "rtc";
    TAG_NAMES["RUBY"] = "ruby";
    TAG_NAMES["S"] = "s";
    TAG_NAMES["SCRIPT"] = "script";
    TAG_NAMES["SEARCH"] = "search";
    TAG_NAMES["SECTION"] = "section";
    TAG_NAMES["SELECT"] = "select";
    TAG_NAMES["SOURCE"] = "source";
    TAG_NAMES["SMALL"] = "small";
    TAG_NAMES["SPAN"] = "span";
    TAG_NAMES["STRIKE"] = "strike";
    TAG_NAMES["STRONG"] = "strong";
    TAG_NAMES["STYLE"] = "style";
    TAG_NAMES["SUB"] = "sub";
    TAG_NAMES["SUMMARY"] = "summary";
    TAG_NAMES["SUP"] = "sup";
    TAG_NAMES["TABLE"] = "table";
    TAG_NAMES["TBODY"] = "tbody";
    TAG_NAMES["TEMPLATE"] = "template";
    TAG_NAMES["TEXTAREA"] = "textarea";
    TAG_NAMES["TFOOT"] = "tfoot";
    TAG_NAMES["TD"] = "td";
    TAG_NAMES["TH"] = "th";
    TAG_NAMES["THEAD"] = "thead";
    TAG_NAMES["TITLE"] = "title";
    TAG_NAMES["TR"] = "tr";
    TAG_NAMES["TRACK"] = "track";
    TAG_NAMES["TT"] = "tt";
    TAG_NAMES["U"] = "u";
    TAG_NAMES["UL"] = "ul";
    TAG_NAMES["SVG"] = "svg";
    TAG_NAMES["VAR"] = "var";
    TAG_NAMES["WBR"] = "wbr";
    TAG_NAMES["XMP"] = "xmp";
})(TAG_NAMES || (TAG_NAMES = {}));
var TAG_ID;
(function(TAG_ID) {
    TAG_ID[TAG_ID["UNKNOWN"] = 0] = "UNKNOWN";
    TAG_ID[TAG_ID["A"] = 1] = "A";
    TAG_ID[TAG_ID["ADDRESS"] = 2] = "ADDRESS";
    TAG_ID[TAG_ID["ANNOTATION_XML"] = 3] = "ANNOTATION_XML";
    TAG_ID[TAG_ID["APPLET"] = 4] = "APPLET";
    TAG_ID[TAG_ID["AREA"] = 5] = "AREA";
    TAG_ID[TAG_ID["ARTICLE"] = 6] = "ARTICLE";
    TAG_ID[TAG_ID["ASIDE"] = 7] = "ASIDE";
    TAG_ID[TAG_ID["B"] = 8] = "B";
    TAG_ID[TAG_ID["BASE"] = 9] = "BASE";
    TAG_ID[TAG_ID["BASEFONT"] = 10] = "BASEFONT";
    TAG_ID[TAG_ID["BGSOUND"] = 11] = "BGSOUND";
    TAG_ID[TAG_ID["BIG"] = 12] = "BIG";
    TAG_ID[TAG_ID["BLOCKQUOTE"] = 13] = "BLOCKQUOTE";
    TAG_ID[TAG_ID["BODY"] = 14] = "BODY";
    TAG_ID[TAG_ID["BR"] = 15] = "BR";
    TAG_ID[TAG_ID["BUTTON"] = 16] = "BUTTON";
    TAG_ID[TAG_ID["CAPTION"] = 17] = "CAPTION";
    TAG_ID[TAG_ID["CENTER"] = 18] = "CENTER";
    TAG_ID[TAG_ID["CODE"] = 19] = "CODE";
    TAG_ID[TAG_ID["COL"] = 20] = "COL";
    TAG_ID[TAG_ID["COLGROUP"] = 21] = "COLGROUP";
    TAG_ID[TAG_ID["DD"] = 22] = "DD";
    TAG_ID[TAG_ID["DESC"] = 23] = "DESC";
    TAG_ID[TAG_ID["DETAILS"] = 24] = "DETAILS";
    TAG_ID[TAG_ID["DIALOG"] = 25] = "DIALOG";
    TAG_ID[TAG_ID["DIR"] = 26] = "DIR";
    TAG_ID[TAG_ID["DIV"] = 27] = "DIV";
    TAG_ID[TAG_ID["DL"] = 28] = "DL";
    TAG_ID[TAG_ID["DT"] = 29] = "DT";
    TAG_ID[TAG_ID["EM"] = 30] = "EM";
    TAG_ID[TAG_ID["EMBED"] = 31] = "EMBED";
    TAG_ID[TAG_ID["FIELDSET"] = 32] = "FIELDSET";
    TAG_ID[TAG_ID["FIGCAPTION"] = 33] = "FIGCAPTION";
    TAG_ID[TAG_ID["FIGURE"] = 34] = "FIGURE";
    TAG_ID[TAG_ID["FONT"] = 35] = "FONT";
    TAG_ID[TAG_ID["FOOTER"] = 36] = "FOOTER";
    TAG_ID[TAG_ID["FOREIGN_OBJECT"] = 37] = "FOREIGN_OBJECT";
    TAG_ID[TAG_ID["FORM"] = 38] = "FORM";
    TAG_ID[TAG_ID["FRAME"] = 39] = "FRAME";
    TAG_ID[TAG_ID["FRAMESET"] = 40] = "FRAMESET";
    TAG_ID[TAG_ID["H1"] = 41] = "H1";
    TAG_ID[TAG_ID["H2"] = 42] = "H2";
    TAG_ID[TAG_ID["H3"] = 43] = "H3";
    TAG_ID[TAG_ID["H4"] = 44] = "H4";
    TAG_ID[TAG_ID["H5"] = 45] = "H5";
    TAG_ID[TAG_ID["H6"] = 46] = "H6";
    TAG_ID[TAG_ID["HEAD"] = 47] = "HEAD";
    TAG_ID[TAG_ID["HEADER"] = 48] = "HEADER";
    TAG_ID[TAG_ID["HGROUP"] = 49] = "HGROUP";
    TAG_ID[TAG_ID["HR"] = 50] = "HR";
    TAG_ID[TAG_ID["HTML"] = 51] = "HTML";
    TAG_ID[TAG_ID["I"] = 52] = "I";
    TAG_ID[TAG_ID["IMG"] = 53] = "IMG";
    TAG_ID[TAG_ID["IMAGE"] = 54] = "IMAGE";
    TAG_ID[TAG_ID["INPUT"] = 55] = "INPUT";
    TAG_ID[TAG_ID["IFRAME"] = 56] = "IFRAME";
    TAG_ID[TAG_ID["KEYGEN"] = 57] = "KEYGEN";
    TAG_ID[TAG_ID["LABEL"] = 58] = "LABEL";
    TAG_ID[TAG_ID["LI"] = 59] = "LI";
    TAG_ID[TAG_ID["LINK"] = 60] = "LINK";
    TAG_ID[TAG_ID["LISTING"] = 61] = "LISTING";
    TAG_ID[TAG_ID["MAIN"] = 62] = "MAIN";
    TAG_ID[TAG_ID["MALIGNMARK"] = 63] = "MALIGNMARK";
    TAG_ID[TAG_ID["MARQUEE"] = 64] = "MARQUEE";
    TAG_ID[TAG_ID["MATH"] = 65] = "MATH";
    TAG_ID[TAG_ID["MENU"] = 66] = "MENU";
    TAG_ID[TAG_ID["META"] = 67] = "META";
    TAG_ID[TAG_ID["MGLYPH"] = 68] = "MGLYPH";
    TAG_ID[TAG_ID["MI"] = 69] = "MI";
    TAG_ID[TAG_ID["MO"] = 70] = "MO";
    TAG_ID[TAG_ID["MN"] = 71] = "MN";
    TAG_ID[TAG_ID["MS"] = 72] = "MS";
    TAG_ID[TAG_ID["MTEXT"] = 73] = "MTEXT";
    TAG_ID[TAG_ID["NAV"] = 74] = "NAV";
    TAG_ID[TAG_ID["NOBR"] = 75] = "NOBR";
    TAG_ID[TAG_ID["NOFRAMES"] = 76] = "NOFRAMES";
    TAG_ID[TAG_ID["NOEMBED"] = 77] = "NOEMBED";
    TAG_ID[TAG_ID["NOSCRIPT"] = 78] = "NOSCRIPT";
    TAG_ID[TAG_ID["OBJECT"] = 79] = "OBJECT";
    TAG_ID[TAG_ID["OL"] = 80] = "OL";
    TAG_ID[TAG_ID["OPTGROUP"] = 81] = "OPTGROUP";
    TAG_ID[TAG_ID["OPTION"] = 82] = "OPTION";
    TAG_ID[TAG_ID["P"] = 83] = "P";
    TAG_ID[TAG_ID["PARAM"] = 84] = "PARAM";
    TAG_ID[TAG_ID["PLAINTEXT"] = 85] = "PLAINTEXT";
    TAG_ID[TAG_ID["PRE"] = 86] = "PRE";
    TAG_ID[TAG_ID["RB"] = 87] = "RB";
    TAG_ID[TAG_ID["RP"] = 88] = "RP";
    TAG_ID[TAG_ID["RT"] = 89] = "RT";
    TAG_ID[TAG_ID["RTC"] = 90] = "RTC";
    TAG_ID[TAG_ID["RUBY"] = 91] = "RUBY";
    TAG_ID[TAG_ID["S"] = 92] = "S";
    TAG_ID[TAG_ID["SCRIPT"] = 93] = "SCRIPT";
    TAG_ID[TAG_ID["SEARCH"] = 94] = "SEARCH";
    TAG_ID[TAG_ID["SECTION"] = 95] = "SECTION";
    TAG_ID[TAG_ID["SELECT"] = 96] = "SELECT";
    TAG_ID[TAG_ID["SOURCE"] = 97] = "SOURCE";
    TAG_ID[TAG_ID["SMALL"] = 98] = "SMALL";
    TAG_ID[TAG_ID["SPAN"] = 99] = "SPAN";
    TAG_ID[TAG_ID["STRIKE"] = 100] = "STRIKE";
    TAG_ID[TAG_ID["STRONG"] = 101] = "STRONG";
    TAG_ID[TAG_ID["STYLE"] = 102] = "STYLE";
    TAG_ID[TAG_ID["SUB"] = 103] = "SUB";
    TAG_ID[TAG_ID["SUMMARY"] = 104] = "SUMMARY";
    TAG_ID[TAG_ID["SUP"] = 105] = "SUP";
    TAG_ID[TAG_ID["TABLE"] = 106] = "TABLE";
    TAG_ID[TAG_ID["TBODY"] = 107] = "TBODY";
    TAG_ID[TAG_ID["TEMPLATE"] = 108] = "TEMPLATE";
    TAG_ID[TAG_ID["TEXTAREA"] = 109] = "TEXTAREA";
    TAG_ID[TAG_ID["TFOOT"] = 110] = "TFOOT";
    TAG_ID[TAG_ID["TD"] = 111] = "TD";
    TAG_ID[TAG_ID["TH"] = 112] = "TH";
    TAG_ID[TAG_ID["THEAD"] = 113] = "THEAD";
    TAG_ID[TAG_ID["TITLE"] = 114] = "TITLE";
    TAG_ID[TAG_ID["TR"] = 115] = "TR";
    TAG_ID[TAG_ID["TRACK"] = 116] = "TRACK";
    TAG_ID[TAG_ID["TT"] = 117] = "TT";
    TAG_ID[TAG_ID["U"] = 118] = "U";
    TAG_ID[TAG_ID["UL"] = 119] = "UL";
    TAG_ID[TAG_ID["SVG"] = 120] = "SVG";
    TAG_ID[TAG_ID["VAR"] = 121] = "VAR";
    TAG_ID[TAG_ID["WBR"] = 122] = "WBR";
    TAG_ID[TAG_ID["XMP"] = 123] = "XMP";
})(TAG_ID || (TAG_ID = {}));
const TAG_NAME_TO_ID = new Map([
    [
        TAG_NAMES.A,
        TAG_ID.A
    ],
    [
        TAG_NAMES.ADDRESS,
        TAG_ID.ADDRESS
    ],
    [
        TAG_NAMES.ANNOTATION_XML,
        TAG_ID.ANNOTATION_XML
    ],
    [
        TAG_NAMES.APPLET,
        TAG_ID.APPLET
    ],
    [
        TAG_NAMES.AREA,
        TAG_ID.AREA
    ],
    [
        TAG_NAMES.ARTICLE,
        TAG_ID.ARTICLE
    ],
    [
        TAG_NAMES.ASIDE,
        TAG_ID.ASIDE
    ],
    [
        TAG_NAMES.B,
        TAG_ID.B
    ],
    [
        TAG_NAMES.BASE,
        TAG_ID.BASE
    ],
    [
        TAG_NAMES.BASEFONT,
        TAG_ID.BASEFONT
    ],
    [
        TAG_NAMES.BGSOUND,
        TAG_ID.BGSOUND
    ],
    [
        TAG_NAMES.BIG,
        TAG_ID.BIG
    ],
    [
        TAG_NAMES.BLOCKQUOTE,
        TAG_ID.BLOCKQUOTE
    ],
    [
        TAG_NAMES.BODY,
        TAG_ID.BODY
    ],
    [
        TAG_NAMES.BR,
        TAG_ID.BR
    ],
    [
        TAG_NAMES.BUTTON,
        TAG_ID.BUTTON
    ],
    [
        TAG_NAMES.CAPTION,
        TAG_ID.CAPTION
    ],
    [
        TAG_NAMES.CENTER,
        TAG_ID.CENTER
    ],
    [
        TAG_NAMES.CODE,
        TAG_ID.CODE
    ],
    [
        TAG_NAMES.COL,
        TAG_ID.COL
    ],
    [
        TAG_NAMES.COLGROUP,
        TAG_ID.COLGROUP
    ],
    [
        TAG_NAMES.DD,
        TAG_ID.DD
    ],
    [
        TAG_NAMES.DESC,
        TAG_ID.DESC
    ],
    [
        TAG_NAMES.DETAILS,
        TAG_ID.DETAILS
    ],
    [
        TAG_NAMES.DIALOG,
        TAG_ID.DIALOG
    ],
    [
        TAG_NAMES.DIR,
        TAG_ID.DIR
    ],
    [
        TAG_NAMES.DIV,
        TAG_ID.DIV
    ],
    [
        TAG_NAMES.DL,
        TAG_ID.DL
    ],
    [
        TAG_NAMES.DT,
        TAG_ID.DT
    ],
    [
        TAG_NAMES.EM,
        TAG_ID.EM
    ],
    [
        TAG_NAMES.EMBED,
        TAG_ID.EMBED
    ],
    [
        TAG_NAMES.FIELDSET,
        TAG_ID.FIELDSET
    ],
    [
        TAG_NAMES.FIGCAPTION,
        TAG_ID.FIGCAPTION
    ],
    [
        TAG_NAMES.FIGURE,
        TAG_ID.FIGURE
    ],
    [
        TAG_NAMES.FONT,
        TAG_ID.FONT
    ],
    [
        TAG_NAMES.FOOTER,
        TAG_ID.FOOTER
    ],
    [
        TAG_NAMES.FOREIGN_OBJECT,
        TAG_ID.FOREIGN_OBJECT
    ],
    [
        TAG_NAMES.FORM,
        TAG_ID.FORM
    ],
    [
        TAG_NAMES.FRAME,
        TAG_ID.FRAME
    ],
    [
        TAG_NAMES.FRAMESET,
        TAG_ID.FRAMESET
    ],
    [
        TAG_NAMES.H1,
        TAG_ID.H1
    ],
    [
        TAG_NAMES.H2,
        TAG_ID.H2
    ],
    [
        TAG_NAMES.H3,
        TAG_ID.H3
    ],
    [
        TAG_NAMES.H4,
        TAG_ID.H4
    ],
    [
        TAG_NAMES.H5,
        TAG_ID.H5
    ],
    [
        TAG_NAMES.H6,
        TAG_ID.H6
    ],
    [
        TAG_NAMES.HEAD,
        TAG_ID.HEAD
    ],
    [
        TAG_NAMES.HEADER,
        TAG_ID.HEADER
    ],
    [
        TAG_NAMES.HGROUP,
        TAG_ID.HGROUP
    ],
    [
        TAG_NAMES.HR,
        TAG_ID.HR
    ],
    [
        TAG_NAMES.HTML,
        TAG_ID.HTML
    ],
    [
        TAG_NAMES.I,
        TAG_ID.I
    ],
    [
        TAG_NAMES.IMG,
        TAG_ID.IMG
    ],
    [
        TAG_NAMES.IMAGE,
        TAG_ID.IMAGE
    ],
    [
        TAG_NAMES.INPUT,
        TAG_ID.INPUT
    ],
    [
        TAG_NAMES.IFRAME,
        TAG_ID.IFRAME
    ],
    [
        TAG_NAMES.KEYGEN,
        TAG_ID.KEYGEN
    ],
    [
        TAG_NAMES.LABEL,
        TAG_ID.LABEL
    ],
    [
        TAG_NAMES.LI,
        TAG_ID.LI
    ],
    [
        TAG_NAMES.LINK,
        TAG_ID.LINK
    ],
    [
        TAG_NAMES.LISTING,
        TAG_ID.LISTING
    ],
    [
        TAG_NAMES.MAIN,
        TAG_ID.MAIN
    ],
    [
        TAG_NAMES.MALIGNMARK,
        TAG_ID.MALIGNMARK
    ],
    [
        TAG_NAMES.MARQUEE,
        TAG_ID.MARQUEE
    ],
    [
        TAG_NAMES.MATH,
        TAG_ID.MATH
    ],
    [
        TAG_NAMES.MENU,
        TAG_ID.MENU
    ],
    [
        TAG_NAMES.META,
        TAG_ID.META
    ],
    [
        TAG_NAMES.MGLYPH,
        TAG_ID.MGLYPH
    ],
    [
        TAG_NAMES.MI,
        TAG_ID.MI
    ],
    [
        TAG_NAMES.MO,
        TAG_ID.MO
    ],
    [
        TAG_NAMES.MN,
        TAG_ID.MN
    ],
    [
        TAG_NAMES.MS,
        TAG_ID.MS
    ],
    [
        TAG_NAMES.MTEXT,
        TAG_ID.MTEXT
    ],
    [
        TAG_NAMES.NAV,
        TAG_ID.NAV
    ],
    [
        TAG_NAMES.NOBR,
        TAG_ID.NOBR
    ],
    [
        TAG_NAMES.NOFRAMES,
        TAG_ID.NOFRAMES
    ],
    [
        TAG_NAMES.NOEMBED,
        TAG_ID.NOEMBED
    ],
    [
        TAG_NAMES.NOSCRIPT,
        TAG_ID.NOSCRIPT
    ],
    [
        TAG_NAMES.OBJECT,
        TAG_ID.OBJECT
    ],
    [
        TAG_NAMES.OL,
        TAG_ID.OL
    ],
    [
        TAG_NAMES.OPTGROUP,
        TAG_ID.OPTGROUP
    ],
    [
        TAG_NAMES.OPTION,
        TAG_ID.OPTION
    ],
    [
        TAG_NAMES.P,
        TAG_ID.P
    ],
    [
        TAG_NAMES.PARAM,
        TAG_ID.PARAM
    ],
    [
        TAG_NAMES.PLAINTEXT,
        TAG_ID.PLAINTEXT
    ],
    [
        TAG_NAMES.PRE,
        TAG_ID.PRE
    ],
    [
        TAG_NAMES.RB,
        TAG_ID.RB
    ],
    [
        TAG_NAMES.RP,
        TAG_ID.RP
    ],
    [
        TAG_NAMES.RT,
        TAG_ID.RT
    ],
    [
        TAG_NAMES.RTC,
        TAG_ID.RTC
    ],
    [
        TAG_NAMES.RUBY,
        TAG_ID.RUBY
    ],
    [
        TAG_NAMES.S,
        TAG_ID.S
    ],
    [
        TAG_NAMES.SCRIPT,
        TAG_ID.SCRIPT
    ],
    [
        TAG_NAMES.SEARCH,
        TAG_ID.SEARCH
    ],
    [
        TAG_NAMES.SECTION,
        TAG_ID.SECTION
    ],
    [
        TAG_NAMES.SELECT,
        TAG_ID.SELECT
    ],
    [
        TAG_NAMES.SOURCE,
        TAG_ID.SOURCE
    ],
    [
        TAG_NAMES.SMALL,
        TAG_ID.SMALL
    ],
    [
        TAG_NAMES.SPAN,
        TAG_ID.SPAN
    ],
    [
        TAG_NAMES.STRIKE,
        TAG_ID.STRIKE
    ],
    [
        TAG_NAMES.STRONG,
        TAG_ID.STRONG
    ],
    [
        TAG_NAMES.STYLE,
        TAG_ID.STYLE
    ],
    [
        TAG_NAMES.SUB,
        TAG_ID.SUB
    ],
    [
        TAG_NAMES.SUMMARY,
        TAG_ID.SUMMARY
    ],
    [
        TAG_NAMES.SUP,
        TAG_ID.SUP
    ],
    [
        TAG_NAMES.TABLE,
        TAG_ID.TABLE
    ],
    [
        TAG_NAMES.TBODY,
        TAG_ID.TBODY
    ],
    [
        TAG_NAMES.TEMPLATE,
        TAG_ID.TEMPLATE
    ],
    [
        TAG_NAMES.TEXTAREA,
        TAG_ID.TEXTAREA
    ],
    [
        TAG_NAMES.TFOOT,
        TAG_ID.TFOOT
    ],
    [
        TAG_NAMES.TD,
        TAG_ID.TD
    ],
    [
        TAG_NAMES.TH,
        TAG_ID.TH
    ],
    [
        TAG_NAMES.THEAD,
        TAG_ID.THEAD
    ],
    [
        TAG_NAMES.TITLE,
        TAG_ID.TITLE
    ],
    [
        TAG_NAMES.TR,
        TAG_ID.TR
    ],
    [
        TAG_NAMES.TRACK,
        TAG_ID.TRACK
    ],
    [
        TAG_NAMES.TT,
        TAG_ID.TT
    ],
    [
        TAG_NAMES.U,
        TAG_ID.U
    ],
    [
        TAG_NAMES.UL,
        TAG_ID.UL
    ],
    [
        TAG_NAMES.SVG,
        TAG_ID.SVG
    ],
    [
        TAG_NAMES.VAR,
        TAG_ID.VAR
    ],
    [
        TAG_NAMES.WBR,
        TAG_ID.WBR
    ],
    [
        TAG_NAMES.XMP,
        TAG_ID.XMP
    ]
]);
function getTagID(tagName) {
    var _a;
    return (_a = TAG_NAME_TO_ID.get(tagName)) !== null && _a !== void 0 ? _a : TAG_ID.UNKNOWN;
}
const $ = TAG_ID;
const SPECIAL_ELEMENTS = {
    [NS.HTML]: new Set([
        $.ADDRESS,
        $.APPLET,
        $.AREA,
        $.ARTICLE,
        $.ASIDE,
        $.BASE,
        $.BASEFONT,
        $.BGSOUND,
        $.BLOCKQUOTE,
        $.BODY,
        $.BR,
        $.BUTTON,
        $.CAPTION,
        $.CENTER,
        $.COL,
        $.COLGROUP,
        $.DD,
        $.DETAILS,
        $.DIR,
        $.DIV,
        $.DL,
        $.DT,
        $.EMBED,
        $.FIELDSET,
        $.FIGCAPTION,
        $.FIGURE,
        $.FOOTER,
        $.FORM,
        $.FRAME,
        $.FRAMESET,
        $.H1,
        $.H2,
        $.H3,
        $.H4,
        $.H5,
        $.H6,
        $.HEAD,
        $.HEADER,
        $.HGROUP,
        $.HR,
        $.HTML,
        $.IFRAME,
        $.IMG,
        $.INPUT,
        $.LI,
        $.LINK,
        $.LISTING,
        $.MAIN,
        $.MARQUEE,
        $.MENU,
        $.META,
        $.NAV,
        $.NOEMBED,
        $.NOFRAMES,
        $.NOSCRIPT,
        $.OBJECT,
        $.OL,
        $.P,
        $.PARAM,
        $.PLAINTEXT,
        $.PRE,
        $.SCRIPT,
        $.SECTION,
        $.SELECT,
        $.SOURCE,
        $.STYLE,
        $.SUMMARY,
        $.TABLE,
        $.TBODY,
        $.TD,
        $.TEMPLATE,
        $.TEXTAREA,
        $.TFOOT,
        $.TH,
        $.THEAD,
        $.TITLE,
        $.TR,
        $.TRACK,
        $.UL,
        $.WBR,
        $.XMP
    ]),
    [NS.MATHML]: new Set([
        $.MI,
        $.MO,
        $.MN,
        $.MS,
        $.MTEXT,
        $.ANNOTATION_XML
    ]),
    [NS.SVG]: new Set([
        $.TITLE,
        $.FOREIGN_OBJECT,
        $.DESC
    ]),
    [NS.XLINK]: new Set(),
    [NS.XML]: new Set(),
    [NS.XMLNS]: new Set()
};
const NUMBERED_HEADERS = new Set([
    $.H1,
    $.H2,
    $.H3,
    $.H4,
    $.H5,
    $.H6
]);
const UNESCAPED_TEXT = new Set([
    TAG_NAMES.STYLE,
    TAG_NAMES.SCRIPT,
    TAG_NAMES.XMP,
    TAG_NAMES.IFRAME,
    TAG_NAMES.NOEMBED,
    TAG_NAMES.NOFRAMES,
    TAG_NAMES.PLAINTEXT
]);
function hasUnescapedText(tn, scriptingEnabled) {
    return UNESCAPED_TEXT.has(tn) || scriptingEnabled && tn === TAG_NAMES.NOSCRIPT;
}
}),
"[project]/coding/projects/LangBot/web/node_modules/parse5/dist/tokenizer/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Tokenizer",
    ()=>Tokenizer,
    "TokenizerMode",
    ()=>TokenizerMode
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tokenizer$2f$preprocessor$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/tokenizer/preprocessor.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/unicode.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/token.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$entities$2f$dist$2f$esm$2f$decode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/entities/dist/esm/decode.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$entities$2f$dist$2f$esm$2f$generated$2f$decode$2d$data$2d$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/entities/dist/esm/generated/decode-data-html.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/error-codes.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/html.js [app-client] (ecmascript)");
;
;
;
;
;
;
//States
var State;
(function(State) {
    State[State["DATA"] = 0] = "DATA";
    State[State["RCDATA"] = 1] = "RCDATA";
    State[State["RAWTEXT"] = 2] = "RAWTEXT";
    State[State["SCRIPT_DATA"] = 3] = "SCRIPT_DATA";
    State[State["PLAINTEXT"] = 4] = "PLAINTEXT";
    State[State["TAG_OPEN"] = 5] = "TAG_OPEN";
    State[State["END_TAG_OPEN"] = 6] = "END_TAG_OPEN";
    State[State["TAG_NAME"] = 7] = "TAG_NAME";
    State[State["RCDATA_LESS_THAN_SIGN"] = 8] = "RCDATA_LESS_THAN_SIGN";
    State[State["RCDATA_END_TAG_OPEN"] = 9] = "RCDATA_END_TAG_OPEN";
    State[State["RCDATA_END_TAG_NAME"] = 10] = "RCDATA_END_TAG_NAME";
    State[State["RAWTEXT_LESS_THAN_SIGN"] = 11] = "RAWTEXT_LESS_THAN_SIGN";
    State[State["RAWTEXT_END_TAG_OPEN"] = 12] = "RAWTEXT_END_TAG_OPEN";
    State[State["RAWTEXT_END_TAG_NAME"] = 13] = "RAWTEXT_END_TAG_NAME";
    State[State["SCRIPT_DATA_LESS_THAN_SIGN"] = 14] = "SCRIPT_DATA_LESS_THAN_SIGN";
    State[State["SCRIPT_DATA_END_TAG_OPEN"] = 15] = "SCRIPT_DATA_END_TAG_OPEN";
    State[State["SCRIPT_DATA_END_TAG_NAME"] = 16] = "SCRIPT_DATA_END_TAG_NAME";
    State[State["SCRIPT_DATA_ESCAPE_START"] = 17] = "SCRIPT_DATA_ESCAPE_START";
    State[State["SCRIPT_DATA_ESCAPE_START_DASH"] = 18] = "SCRIPT_DATA_ESCAPE_START_DASH";
    State[State["SCRIPT_DATA_ESCAPED"] = 19] = "SCRIPT_DATA_ESCAPED";
    State[State["SCRIPT_DATA_ESCAPED_DASH"] = 20] = "SCRIPT_DATA_ESCAPED_DASH";
    State[State["SCRIPT_DATA_ESCAPED_DASH_DASH"] = 21] = "SCRIPT_DATA_ESCAPED_DASH_DASH";
    State[State["SCRIPT_DATA_ESCAPED_LESS_THAN_SIGN"] = 22] = "SCRIPT_DATA_ESCAPED_LESS_THAN_SIGN";
    State[State["SCRIPT_DATA_ESCAPED_END_TAG_OPEN"] = 23] = "SCRIPT_DATA_ESCAPED_END_TAG_OPEN";
    State[State["SCRIPT_DATA_ESCAPED_END_TAG_NAME"] = 24] = "SCRIPT_DATA_ESCAPED_END_TAG_NAME";
    State[State["SCRIPT_DATA_DOUBLE_ESCAPE_START"] = 25] = "SCRIPT_DATA_DOUBLE_ESCAPE_START";
    State[State["SCRIPT_DATA_DOUBLE_ESCAPED"] = 26] = "SCRIPT_DATA_DOUBLE_ESCAPED";
    State[State["SCRIPT_DATA_DOUBLE_ESCAPED_DASH"] = 27] = "SCRIPT_DATA_DOUBLE_ESCAPED_DASH";
    State[State["SCRIPT_DATA_DOUBLE_ESCAPED_DASH_DASH"] = 28] = "SCRIPT_DATA_DOUBLE_ESCAPED_DASH_DASH";
    State[State["SCRIPT_DATA_DOUBLE_ESCAPED_LESS_THAN_SIGN"] = 29] = "SCRIPT_DATA_DOUBLE_ESCAPED_LESS_THAN_SIGN";
    State[State["SCRIPT_DATA_DOUBLE_ESCAPE_END"] = 30] = "SCRIPT_DATA_DOUBLE_ESCAPE_END";
    State[State["BEFORE_ATTRIBUTE_NAME"] = 31] = "BEFORE_ATTRIBUTE_NAME";
    State[State["ATTRIBUTE_NAME"] = 32] = "ATTRIBUTE_NAME";
    State[State["AFTER_ATTRIBUTE_NAME"] = 33] = "AFTER_ATTRIBUTE_NAME";
    State[State["BEFORE_ATTRIBUTE_VALUE"] = 34] = "BEFORE_ATTRIBUTE_VALUE";
    State[State["ATTRIBUTE_VALUE_DOUBLE_QUOTED"] = 35] = "ATTRIBUTE_VALUE_DOUBLE_QUOTED";
    State[State["ATTRIBUTE_VALUE_SINGLE_QUOTED"] = 36] = "ATTRIBUTE_VALUE_SINGLE_QUOTED";
    State[State["ATTRIBUTE_VALUE_UNQUOTED"] = 37] = "ATTRIBUTE_VALUE_UNQUOTED";
    State[State["AFTER_ATTRIBUTE_VALUE_QUOTED"] = 38] = "AFTER_ATTRIBUTE_VALUE_QUOTED";
    State[State["SELF_CLOSING_START_TAG"] = 39] = "SELF_CLOSING_START_TAG";
    State[State["BOGUS_COMMENT"] = 40] = "BOGUS_COMMENT";
    State[State["MARKUP_DECLARATION_OPEN"] = 41] = "MARKUP_DECLARATION_OPEN";
    State[State["COMMENT_START"] = 42] = "COMMENT_START";
    State[State["COMMENT_START_DASH"] = 43] = "COMMENT_START_DASH";
    State[State["COMMENT"] = 44] = "COMMENT";
    State[State["COMMENT_LESS_THAN_SIGN"] = 45] = "COMMENT_LESS_THAN_SIGN";
    State[State["COMMENT_LESS_THAN_SIGN_BANG"] = 46] = "COMMENT_LESS_THAN_SIGN_BANG";
    State[State["COMMENT_LESS_THAN_SIGN_BANG_DASH"] = 47] = "COMMENT_LESS_THAN_SIGN_BANG_DASH";
    State[State["COMMENT_LESS_THAN_SIGN_BANG_DASH_DASH"] = 48] = "COMMENT_LESS_THAN_SIGN_BANG_DASH_DASH";
    State[State["COMMENT_END_DASH"] = 49] = "COMMENT_END_DASH";
    State[State["COMMENT_END"] = 50] = "COMMENT_END";
    State[State["COMMENT_END_BANG"] = 51] = "COMMENT_END_BANG";
    State[State["DOCTYPE"] = 52] = "DOCTYPE";
    State[State["BEFORE_DOCTYPE_NAME"] = 53] = "BEFORE_DOCTYPE_NAME";
    State[State["DOCTYPE_NAME"] = 54] = "DOCTYPE_NAME";
    State[State["AFTER_DOCTYPE_NAME"] = 55] = "AFTER_DOCTYPE_NAME";
    State[State["AFTER_DOCTYPE_PUBLIC_KEYWORD"] = 56] = "AFTER_DOCTYPE_PUBLIC_KEYWORD";
    State[State["BEFORE_DOCTYPE_PUBLIC_IDENTIFIER"] = 57] = "BEFORE_DOCTYPE_PUBLIC_IDENTIFIER";
    State[State["DOCTYPE_PUBLIC_IDENTIFIER_DOUBLE_QUOTED"] = 58] = "DOCTYPE_PUBLIC_IDENTIFIER_DOUBLE_QUOTED";
    State[State["DOCTYPE_PUBLIC_IDENTIFIER_SINGLE_QUOTED"] = 59] = "DOCTYPE_PUBLIC_IDENTIFIER_SINGLE_QUOTED";
    State[State["AFTER_DOCTYPE_PUBLIC_IDENTIFIER"] = 60] = "AFTER_DOCTYPE_PUBLIC_IDENTIFIER";
    State[State["BETWEEN_DOCTYPE_PUBLIC_AND_SYSTEM_IDENTIFIERS"] = 61] = "BETWEEN_DOCTYPE_PUBLIC_AND_SYSTEM_IDENTIFIERS";
    State[State["AFTER_DOCTYPE_SYSTEM_KEYWORD"] = 62] = "AFTER_DOCTYPE_SYSTEM_KEYWORD";
    State[State["BEFORE_DOCTYPE_SYSTEM_IDENTIFIER"] = 63] = "BEFORE_DOCTYPE_SYSTEM_IDENTIFIER";
    State[State["DOCTYPE_SYSTEM_IDENTIFIER_DOUBLE_QUOTED"] = 64] = "DOCTYPE_SYSTEM_IDENTIFIER_DOUBLE_QUOTED";
    State[State["DOCTYPE_SYSTEM_IDENTIFIER_SINGLE_QUOTED"] = 65] = "DOCTYPE_SYSTEM_IDENTIFIER_SINGLE_QUOTED";
    State[State["AFTER_DOCTYPE_SYSTEM_IDENTIFIER"] = 66] = "AFTER_DOCTYPE_SYSTEM_IDENTIFIER";
    State[State["BOGUS_DOCTYPE"] = 67] = "BOGUS_DOCTYPE";
    State[State["CDATA_SECTION"] = 68] = "CDATA_SECTION";
    State[State["CDATA_SECTION_BRACKET"] = 69] = "CDATA_SECTION_BRACKET";
    State[State["CDATA_SECTION_END"] = 70] = "CDATA_SECTION_END";
    State[State["CHARACTER_REFERENCE"] = 71] = "CHARACTER_REFERENCE";
    State[State["AMBIGUOUS_AMPERSAND"] = 72] = "AMBIGUOUS_AMPERSAND";
})(State || (State = {}));
const TokenizerMode = {
    DATA: State.DATA,
    RCDATA: State.RCDATA,
    RAWTEXT: State.RAWTEXT,
    SCRIPT_DATA: State.SCRIPT_DATA,
    PLAINTEXT: State.PLAINTEXT,
    CDATA_SECTION: State.CDATA_SECTION
};
//Utils
//OPTIMIZATION: these utility functions should not be moved out of this module. V8 Crankshaft will not inline
//this functions if they will be situated in another module due to context switch.
//Always perform inlining check before modifying this functions ('node --trace-inlining').
function isAsciiDigit(cp) {
    return cp >= __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].DIGIT_0 && cp <= __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].DIGIT_9;
}
function isAsciiUpper(cp) {
    return cp >= __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LATIN_CAPITAL_A && cp <= __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LATIN_CAPITAL_Z;
}
function isAsciiLower(cp) {
    return cp >= __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LATIN_SMALL_A && cp <= __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LATIN_SMALL_Z;
}
function isAsciiLetter(cp) {
    return isAsciiLower(cp) || isAsciiUpper(cp);
}
function isAsciiAlphaNumeric(cp) {
    return isAsciiLetter(cp) || isAsciiDigit(cp);
}
function toAsciiLower(cp) {
    return cp + 32;
}
function isWhitespace(cp) {
    return cp === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SPACE || cp === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED || cp === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].TABULATION || cp === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].FORM_FEED;
}
function isScriptDataDoubleEscapeSequenceEnd(cp) {
    return isWhitespace(cp) || cp === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SOLIDUS || cp === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN;
}
function getErrorForNumericCharacterReference(code) {
    if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL) {
        return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].nullCharacterReference;
    } else if (code > 1114111) {
        return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].characterReferenceOutsideUnicodeRange;
    } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isSurrogate"])(code)) {
        return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].surrogateCharacterReference;
    } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isUndefinedCodePoint"])(code)) {
        return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].noncharacterCharacterReference;
    } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isControlCodePoint"])(code) || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].CARRIAGE_RETURN) {
        return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].controlCharacterReference;
    }
    return null;
}
class Tokenizer {
    constructor(options, handler){
        this.options = options;
        this.handler = handler;
        this.paused = false;
        /** Ensures that the parsing loop isn't run multiple times at once. */ this.inLoop = false;
        /**
         * Indicates that the current adjusted node exists, is not an element in the HTML namespace,
         * and that it is not an integration point for either MathML or HTML.
         *
         * @see {@link https://html.spec.whatwg.org/multipage/parsing.html#tree-construction}
         */ this.inForeignNode = false;
        this.lastStartTagName = '';
        this.active = false;
        this.state = State.DATA;
        this.returnState = State.DATA;
        this.entityStartPos = 0;
        this.consumedAfterSnapshot = -1;
        this.currentCharacterToken = null;
        this.currentToken = null;
        this.currentAttr = {
            name: '',
            value: ''
        };
        this.preprocessor = new __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tokenizer$2f$preprocessor$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Preprocessor"](handler);
        this.currentLocation = this.getCurrentLocation(-1);
        this.entityDecoder = new __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$entities$2f$dist$2f$esm$2f$decode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["EntityDecoder"](__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$entities$2f$dist$2f$esm$2f$generated$2f$decode$2d$data$2d$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["htmlDecodeTree"], (cp, consumed)=>{
            // Note: Set `pos` _before_ flushing, as flushing might drop
            // the current chunk and invalidate `entityStartPos`.
            this.preprocessor.pos = this.entityStartPos + consumed - 1;
            this._flushCodePointConsumedAsCharacterReference(cp);
        }, handler.onParseError ? {
            missingSemicolonAfterCharacterReference: ()=>{
                this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingSemicolonAfterCharacterReference, 1);
            },
            absenceOfDigitsInNumericCharacterReference: (consumed)=>{
                this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].absenceOfDigitsInNumericCharacterReference, this.entityStartPos - this.preprocessor.pos + consumed);
            },
            validateNumericCharacterReference: (code)=>{
                const error = getErrorForNumericCharacterReference(code);
                if (error) this._err(error, 1);
            }
        } : undefined);
    }
    //Errors
    _err(code, cpOffset = 0) {
        var _a, _b;
        (_b = (_a = this.handler).onParseError) === null || _b === void 0 ? void 0 : _b.call(_a, this.preprocessor.getError(code, cpOffset));
    }
    // NOTE: `offset` may never run across line boundaries.
    getCurrentLocation(offset) {
        if (!this.options.sourceCodeLocationInfo) {
            return null;
        }
        return {
            startLine: this.preprocessor.line,
            startCol: this.preprocessor.col - offset,
            startOffset: this.preprocessor.offset - offset,
            endLine: -1,
            endCol: -1,
            endOffset: -1
        };
    }
    _runParsingLoop() {
        if (this.inLoop) return;
        this.inLoop = true;
        while(this.active && !this.paused){
            this.consumedAfterSnapshot = 0;
            const cp = this._consume();
            if (!this._ensureHibernation()) {
                this._callState(cp);
            }
        }
        this.inLoop = false;
    }
    //API
    pause() {
        this.paused = true;
    }
    resume(writeCallback) {
        if (!this.paused) {
            throw new Error('Parser was already resumed');
        }
        this.paused = false;
        // Necessary for synchronous resume.
        if (this.inLoop) return;
        this._runParsingLoop();
        if (!this.paused) {
            writeCallback === null || writeCallback === void 0 ? void 0 : writeCallback();
        }
    }
    write(chunk, isLastChunk, writeCallback) {
        this.active = true;
        this.preprocessor.write(chunk, isLastChunk);
        this._runParsingLoop();
        if (!this.paused) {
            writeCallback === null || writeCallback === void 0 ? void 0 : writeCallback();
        }
    }
    insertHtmlAtCurrentPos(chunk) {
        this.active = true;
        this.preprocessor.insertHtmlAtCurrentPos(chunk);
        this._runParsingLoop();
    }
    //Hibernation
    _ensureHibernation() {
        if (this.preprocessor.endOfChunkHit) {
            this.preprocessor.retreat(this.consumedAfterSnapshot);
            this.consumedAfterSnapshot = 0;
            this.active = false;
            return true;
        }
        return false;
    }
    //Consumption
    _consume() {
        this.consumedAfterSnapshot++;
        return this.preprocessor.advance();
    }
    _advanceBy(count) {
        this.consumedAfterSnapshot += count;
        for(let i = 0; i < count; i++){
            this.preprocessor.advance();
        }
    }
    _consumeSequenceIfMatch(pattern, caseSensitive) {
        if (this.preprocessor.startsWith(pattern, caseSensitive)) {
            // We will already have consumed one character before calling this method.
            this._advanceBy(pattern.length - 1);
            return true;
        }
        return false;
    }
    //Token creation
    _createStartTagToken() {
        this.currentToken = {
            type: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].START_TAG,
            tagName: '',
            tagID: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].UNKNOWN,
            selfClosing: false,
            ackSelfClosing: false,
            attrs: [],
            location: this.getCurrentLocation(1)
        };
    }
    _createEndTagToken() {
        this.currentToken = {
            type: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].END_TAG,
            tagName: '',
            tagID: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].UNKNOWN,
            selfClosing: false,
            ackSelfClosing: false,
            attrs: [],
            location: this.getCurrentLocation(2)
        };
    }
    _createCommentToken(offset) {
        this.currentToken = {
            type: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].COMMENT,
            data: '',
            location: this.getCurrentLocation(offset)
        };
    }
    _createDoctypeToken(initialName) {
        this.currentToken = {
            type: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].DOCTYPE,
            name: initialName,
            forceQuirks: false,
            publicId: null,
            systemId: null,
            location: this.currentLocation
        };
    }
    _createCharacterToken(type, chars) {
        this.currentCharacterToken = {
            type,
            chars,
            location: this.currentLocation
        };
    }
    //Tag attributes
    _createAttr(attrNameFirstCh) {
        this.currentAttr = {
            name: attrNameFirstCh,
            value: ''
        };
        this.currentLocation = this.getCurrentLocation(0);
    }
    _leaveAttrName() {
        var _a;
        var _b;
        const token = this.currentToken;
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTokenAttr"])(token, this.currentAttr.name) === null) {
            token.attrs.push(this.currentAttr);
            if (token.location && this.currentLocation) {
                const attrLocations = (_a = (_b = token.location).attrs) !== null && _a !== void 0 ? _a : _b.attrs = Object.create(null);
                attrLocations[this.currentAttr.name] = this.currentLocation;
                // Set end location
                this._leaveAttrValue();
            }
        } else {
            this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].duplicateAttribute);
        }
    }
    _leaveAttrValue() {
        if (this.currentLocation) {
            this.currentLocation.endLine = this.preprocessor.line;
            this.currentLocation.endCol = this.preprocessor.col;
            this.currentLocation.endOffset = this.preprocessor.offset;
        }
    }
    //Token emission
    prepareToken(ct) {
        this._emitCurrentCharacterToken(ct.location);
        this.currentToken = null;
        if (ct.location) {
            ct.location.endLine = this.preprocessor.line;
            ct.location.endCol = this.preprocessor.col + 1;
            ct.location.endOffset = this.preprocessor.offset + 1;
        }
        this.currentLocation = this.getCurrentLocation(-1);
    }
    emitCurrentTagToken() {
        const ct = this.currentToken;
        this.prepareToken(ct);
        ct.tagID = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTagID"])(ct.tagName);
        if (ct.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].START_TAG) {
            this.lastStartTagName = ct.tagName;
            this.handler.onStartTag(ct);
        } else {
            if (ct.attrs.length > 0) {
                this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].endTagWithAttributes);
            }
            if (ct.selfClosing) {
                this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].endTagWithTrailingSolidus);
            }
            this.handler.onEndTag(ct);
        }
        this.preprocessor.dropParsedChunk();
    }
    emitCurrentComment(ct) {
        this.prepareToken(ct);
        this.handler.onComment(ct);
        this.preprocessor.dropParsedChunk();
    }
    emitCurrentDoctype(ct) {
        this.prepareToken(ct);
        this.handler.onDoctype(ct);
        this.preprocessor.dropParsedChunk();
    }
    _emitCurrentCharacterToken(nextLocation) {
        if (this.currentCharacterToken) {
            //NOTE: if we have a pending character token, make it's end location equal to the
            //current token's start location.
            if (nextLocation && this.currentCharacterToken.location) {
                this.currentCharacterToken.location.endLine = nextLocation.startLine;
                this.currentCharacterToken.location.endCol = nextLocation.startCol;
                this.currentCharacterToken.location.endOffset = nextLocation.startOffset;
            }
            switch(this.currentCharacterToken.type){
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].CHARACTER:
                    {
                        this.handler.onCharacter(this.currentCharacterToken);
                        break;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].NULL_CHARACTER:
                    {
                        this.handler.onNullCharacter(this.currentCharacterToken);
                        break;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].WHITESPACE_CHARACTER:
                    {
                        this.handler.onWhitespaceCharacter(this.currentCharacterToken);
                        break;
                    }
            }
            this.currentCharacterToken = null;
        }
    }
    _emitEOFToken() {
        const location = this.getCurrentLocation(0);
        if (location) {
            location.endLine = location.startLine;
            location.endCol = location.startCol;
            location.endOffset = location.startOffset;
        }
        this._emitCurrentCharacterToken(location);
        this.handler.onEof({
            type: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].EOF,
            location
        });
        this.active = false;
    }
    //Characters emission
    //OPTIMIZATION: The specification uses only one type of character token (one token per character).
    //This causes a huge memory overhead and a lot of unnecessary parser loops. parse5 uses 3 groups of characters.
    //If we have a sequence of characters that belong to the same group, the parser can process it
    //as a single solid character token.
    //So, there are 3 types of character tokens in parse5:
    //1)TokenType.NULL_CHARACTER - \u0000-character sequences (e.g. '\u0000\u0000\u0000')
    //2)TokenType.WHITESPACE_CHARACTER - any whitespace/new-line character sequences (e.g. '\n  \r\t   \f')
    //3)TokenType.CHARACTER - any character sequence which don't belong to groups 1 and 2 (e.g. 'abcdef1234@@#$%^')
    _appendCharToCurrentCharacterToken(type, ch) {
        if (this.currentCharacterToken) {
            if (this.currentCharacterToken.type === type) {
                this.currentCharacterToken.chars += ch;
                return;
            } else {
                this.currentLocation = this.getCurrentLocation(0);
                this._emitCurrentCharacterToken(this.currentLocation);
                this.preprocessor.dropParsedChunk();
            }
        }
        this._createCharacterToken(type, ch);
    }
    _emitCodePoint(cp) {
        const type = isWhitespace(cp) ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].WHITESPACE_CHARACTER : cp === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].NULL_CHARACTER : __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].CHARACTER;
        this._appendCharToCurrentCharacterToken(type, String.fromCodePoint(cp));
    }
    //NOTE: used when we emit characters explicitly.
    //This is always for non-whitespace and non-null characters, which allows us to avoid additional checks.
    _emitChars(ch) {
        this._appendCharToCurrentCharacterToken(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].CHARACTER, ch);
    }
    // Character reference helpers
    _startCharacterReference() {
        this.returnState = this.state;
        this.state = State.CHARACTER_REFERENCE;
        this.entityStartPos = this.preprocessor.pos;
        this.entityDecoder.startEntity(this._isCharacterReferenceInAttribute() ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$entities$2f$dist$2f$esm$2f$decode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["DecodingMode"].Attribute : __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$entities$2f$dist$2f$esm$2f$decode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["DecodingMode"].Legacy);
    }
    _isCharacterReferenceInAttribute() {
        return this.returnState === State.ATTRIBUTE_VALUE_DOUBLE_QUOTED || this.returnState === State.ATTRIBUTE_VALUE_SINGLE_QUOTED || this.returnState === State.ATTRIBUTE_VALUE_UNQUOTED;
    }
    _flushCodePointConsumedAsCharacterReference(cp) {
        if (this._isCharacterReferenceInAttribute()) {
            this.currentAttr.value += String.fromCodePoint(cp);
        } else {
            this._emitCodePoint(cp);
        }
    }
    // Calling states this way turns out to be much faster than any other approach.
    _callState(cp) {
        switch(this.state){
            case State.DATA:
                {
                    this._stateData(cp);
                    break;
                }
            case State.RCDATA:
                {
                    this._stateRcdata(cp);
                    break;
                }
            case State.RAWTEXT:
                {
                    this._stateRawtext(cp);
                    break;
                }
            case State.SCRIPT_DATA:
                {
                    this._stateScriptData(cp);
                    break;
                }
            case State.PLAINTEXT:
                {
                    this._statePlaintext(cp);
                    break;
                }
            case State.TAG_OPEN:
                {
                    this._stateTagOpen(cp);
                    break;
                }
            case State.END_TAG_OPEN:
                {
                    this._stateEndTagOpen(cp);
                    break;
                }
            case State.TAG_NAME:
                {
                    this._stateTagName(cp);
                    break;
                }
            case State.RCDATA_LESS_THAN_SIGN:
                {
                    this._stateRcdataLessThanSign(cp);
                    break;
                }
            case State.RCDATA_END_TAG_OPEN:
                {
                    this._stateRcdataEndTagOpen(cp);
                    break;
                }
            case State.RCDATA_END_TAG_NAME:
                {
                    this._stateRcdataEndTagName(cp);
                    break;
                }
            case State.RAWTEXT_LESS_THAN_SIGN:
                {
                    this._stateRawtextLessThanSign(cp);
                    break;
                }
            case State.RAWTEXT_END_TAG_OPEN:
                {
                    this._stateRawtextEndTagOpen(cp);
                    break;
                }
            case State.RAWTEXT_END_TAG_NAME:
                {
                    this._stateRawtextEndTagName(cp);
                    break;
                }
            case State.SCRIPT_DATA_LESS_THAN_SIGN:
                {
                    this._stateScriptDataLessThanSign(cp);
                    break;
                }
            case State.SCRIPT_DATA_END_TAG_OPEN:
                {
                    this._stateScriptDataEndTagOpen(cp);
                    break;
                }
            case State.SCRIPT_DATA_END_TAG_NAME:
                {
                    this._stateScriptDataEndTagName(cp);
                    break;
                }
            case State.SCRIPT_DATA_ESCAPE_START:
                {
                    this._stateScriptDataEscapeStart(cp);
                    break;
                }
            case State.SCRIPT_DATA_ESCAPE_START_DASH:
                {
                    this._stateScriptDataEscapeStartDash(cp);
                    break;
                }
            case State.SCRIPT_DATA_ESCAPED:
                {
                    this._stateScriptDataEscaped(cp);
                    break;
                }
            case State.SCRIPT_DATA_ESCAPED_DASH:
                {
                    this._stateScriptDataEscapedDash(cp);
                    break;
                }
            case State.SCRIPT_DATA_ESCAPED_DASH_DASH:
                {
                    this._stateScriptDataEscapedDashDash(cp);
                    break;
                }
            case State.SCRIPT_DATA_ESCAPED_LESS_THAN_SIGN:
                {
                    this._stateScriptDataEscapedLessThanSign(cp);
                    break;
                }
            case State.SCRIPT_DATA_ESCAPED_END_TAG_OPEN:
                {
                    this._stateScriptDataEscapedEndTagOpen(cp);
                    break;
                }
            case State.SCRIPT_DATA_ESCAPED_END_TAG_NAME:
                {
                    this._stateScriptDataEscapedEndTagName(cp);
                    break;
                }
            case State.SCRIPT_DATA_DOUBLE_ESCAPE_START:
                {
                    this._stateScriptDataDoubleEscapeStart(cp);
                    break;
                }
            case State.SCRIPT_DATA_DOUBLE_ESCAPED:
                {
                    this._stateScriptDataDoubleEscaped(cp);
                    break;
                }
            case State.SCRIPT_DATA_DOUBLE_ESCAPED_DASH:
                {
                    this._stateScriptDataDoubleEscapedDash(cp);
                    break;
                }
            case State.SCRIPT_DATA_DOUBLE_ESCAPED_DASH_DASH:
                {
                    this._stateScriptDataDoubleEscapedDashDash(cp);
                    break;
                }
            case State.SCRIPT_DATA_DOUBLE_ESCAPED_LESS_THAN_SIGN:
                {
                    this._stateScriptDataDoubleEscapedLessThanSign(cp);
                    break;
                }
            case State.SCRIPT_DATA_DOUBLE_ESCAPE_END:
                {
                    this._stateScriptDataDoubleEscapeEnd(cp);
                    break;
                }
            case State.BEFORE_ATTRIBUTE_NAME:
                {
                    this._stateBeforeAttributeName(cp);
                    break;
                }
            case State.ATTRIBUTE_NAME:
                {
                    this._stateAttributeName(cp);
                    break;
                }
            case State.AFTER_ATTRIBUTE_NAME:
                {
                    this._stateAfterAttributeName(cp);
                    break;
                }
            case State.BEFORE_ATTRIBUTE_VALUE:
                {
                    this._stateBeforeAttributeValue(cp);
                    break;
                }
            case State.ATTRIBUTE_VALUE_DOUBLE_QUOTED:
                {
                    this._stateAttributeValueDoubleQuoted(cp);
                    break;
                }
            case State.ATTRIBUTE_VALUE_SINGLE_QUOTED:
                {
                    this._stateAttributeValueSingleQuoted(cp);
                    break;
                }
            case State.ATTRIBUTE_VALUE_UNQUOTED:
                {
                    this._stateAttributeValueUnquoted(cp);
                    break;
                }
            case State.AFTER_ATTRIBUTE_VALUE_QUOTED:
                {
                    this._stateAfterAttributeValueQuoted(cp);
                    break;
                }
            case State.SELF_CLOSING_START_TAG:
                {
                    this._stateSelfClosingStartTag(cp);
                    break;
                }
            case State.BOGUS_COMMENT:
                {
                    this._stateBogusComment(cp);
                    break;
                }
            case State.MARKUP_DECLARATION_OPEN:
                {
                    this._stateMarkupDeclarationOpen(cp);
                    break;
                }
            case State.COMMENT_START:
                {
                    this._stateCommentStart(cp);
                    break;
                }
            case State.COMMENT_START_DASH:
                {
                    this._stateCommentStartDash(cp);
                    break;
                }
            case State.COMMENT:
                {
                    this._stateComment(cp);
                    break;
                }
            case State.COMMENT_LESS_THAN_SIGN:
                {
                    this._stateCommentLessThanSign(cp);
                    break;
                }
            case State.COMMENT_LESS_THAN_SIGN_BANG:
                {
                    this._stateCommentLessThanSignBang(cp);
                    break;
                }
            case State.COMMENT_LESS_THAN_SIGN_BANG_DASH:
                {
                    this._stateCommentLessThanSignBangDash(cp);
                    break;
                }
            case State.COMMENT_LESS_THAN_SIGN_BANG_DASH_DASH:
                {
                    this._stateCommentLessThanSignBangDashDash(cp);
                    break;
                }
            case State.COMMENT_END_DASH:
                {
                    this._stateCommentEndDash(cp);
                    break;
                }
            case State.COMMENT_END:
                {
                    this._stateCommentEnd(cp);
                    break;
                }
            case State.COMMENT_END_BANG:
                {
                    this._stateCommentEndBang(cp);
                    break;
                }
            case State.DOCTYPE:
                {
                    this._stateDoctype(cp);
                    break;
                }
            case State.BEFORE_DOCTYPE_NAME:
                {
                    this._stateBeforeDoctypeName(cp);
                    break;
                }
            case State.DOCTYPE_NAME:
                {
                    this._stateDoctypeName(cp);
                    break;
                }
            case State.AFTER_DOCTYPE_NAME:
                {
                    this._stateAfterDoctypeName(cp);
                    break;
                }
            case State.AFTER_DOCTYPE_PUBLIC_KEYWORD:
                {
                    this._stateAfterDoctypePublicKeyword(cp);
                    break;
                }
            case State.BEFORE_DOCTYPE_PUBLIC_IDENTIFIER:
                {
                    this._stateBeforeDoctypePublicIdentifier(cp);
                    break;
                }
            case State.DOCTYPE_PUBLIC_IDENTIFIER_DOUBLE_QUOTED:
                {
                    this._stateDoctypePublicIdentifierDoubleQuoted(cp);
                    break;
                }
            case State.DOCTYPE_PUBLIC_IDENTIFIER_SINGLE_QUOTED:
                {
                    this._stateDoctypePublicIdentifierSingleQuoted(cp);
                    break;
                }
            case State.AFTER_DOCTYPE_PUBLIC_IDENTIFIER:
                {
                    this._stateAfterDoctypePublicIdentifier(cp);
                    break;
                }
            case State.BETWEEN_DOCTYPE_PUBLIC_AND_SYSTEM_IDENTIFIERS:
                {
                    this._stateBetweenDoctypePublicAndSystemIdentifiers(cp);
                    break;
                }
            case State.AFTER_DOCTYPE_SYSTEM_KEYWORD:
                {
                    this._stateAfterDoctypeSystemKeyword(cp);
                    break;
                }
            case State.BEFORE_DOCTYPE_SYSTEM_IDENTIFIER:
                {
                    this._stateBeforeDoctypeSystemIdentifier(cp);
                    break;
                }
            case State.DOCTYPE_SYSTEM_IDENTIFIER_DOUBLE_QUOTED:
                {
                    this._stateDoctypeSystemIdentifierDoubleQuoted(cp);
                    break;
                }
            case State.DOCTYPE_SYSTEM_IDENTIFIER_SINGLE_QUOTED:
                {
                    this._stateDoctypeSystemIdentifierSingleQuoted(cp);
                    break;
                }
            case State.AFTER_DOCTYPE_SYSTEM_IDENTIFIER:
                {
                    this._stateAfterDoctypeSystemIdentifier(cp);
                    break;
                }
            case State.BOGUS_DOCTYPE:
                {
                    this._stateBogusDoctype(cp);
                    break;
                }
            case State.CDATA_SECTION:
                {
                    this._stateCdataSection(cp);
                    break;
                }
            case State.CDATA_SECTION_BRACKET:
                {
                    this._stateCdataSectionBracket(cp);
                    break;
                }
            case State.CDATA_SECTION_END:
                {
                    this._stateCdataSectionEnd(cp);
                    break;
                }
            case State.CHARACTER_REFERENCE:
                {
                    this._stateCharacterReference();
                    break;
                }
            case State.AMBIGUOUS_AMPERSAND:
                {
                    this._stateAmbiguousAmpersand(cp);
                    break;
                }
            default:
                {
                    throw new Error('Unknown state');
                }
        }
    }
    // State machine
    // Data state
    //------------------------------------------------------------------
    _stateData(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LESS_THAN_SIGN:
                {
                    this.state = State.TAG_OPEN;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].AMPERSAND:
                {
                    this._startCharacterReference();
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    this._emitCodePoint(cp);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._emitCodePoint(cp);
                }
        }
    }
    //  RCDATA state
    //------------------------------------------------------------------
    _stateRcdata(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].AMPERSAND:
                {
                    this._startCharacterReference();
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LESS_THAN_SIGN:
                {
                    this.state = State.RCDATA_LESS_THAN_SIGN;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    this._emitChars(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"]);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._emitCodePoint(cp);
                }
        }
    }
    // RAWTEXT state
    //------------------------------------------------------------------
    _stateRawtext(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LESS_THAN_SIGN:
                {
                    this.state = State.RAWTEXT_LESS_THAN_SIGN;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    this._emitChars(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"]);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._emitCodePoint(cp);
                }
        }
    }
    // Script data state
    //------------------------------------------------------------------
    _stateScriptData(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LESS_THAN_SIGN:
                {
                    this.state = State.SCRIPT_DATA_LESS_THAN_SIGN;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    this._emitChars(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"]);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._emitCodePoint(cp);
                }
        }
    }
    // PLAINTEXT state
    //------------------------------------------------------------------
    _statePlaintext(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    this._emitChars(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"]);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._emitCodePoint(cp);
                }
        }
    }
    // Tag open state
    //------------------------------------------------------------------
    _stateTagOpen(cp) {
        if (isAsciiLetter(cp)) {
            this._createStartTagToken();
            this.state = State.TAG_NAME;
            this._stateTagName(cp);
        } else switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EXCLAMATION_MARK:
                {
                    this.state = State.MARKUP_DECLARATION_OPEN;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SOLIDUS:
                {
                    this.state = State.END_TAG_OPEN;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].QUESTION_MARK:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedQuestionMarkInsteadOfTagName);
                    this._createCommentToken(1);
                    this.state = State.BOGUS_COMMENT;
                    this._stateBogusComment(cp);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofBeforeTagName);
                    this._emitChars('<');
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].invalidFirstCharacterOfTagName);
                    this._emitChars('<');
                    this.state = State.DATA;
                    this._stateData(cp);
                }
        }
    }
    // End tag open state
    //------------------------------------------------------------------
    _stateEndTagOpen(cp) {
        if (isAsciiLetter(cp)) {
            this._createEndTagToken();
            this.state = State.TAG_NAME;
            this._stateTagName(cp);
        } else switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingEndTagName);
                    this.state = State.DATA;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofBeforeTagName);
                    this._emitChars('</');
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].invalidFirstCharacterOfTagName);
                    this._createCommentToken(2);
                    this.state = State.BOGUS_COMMENT;
                    this._stateBogusComment(cp);
                }
        }
    }
    // Tag name state
    //------------------------------------------------------------------
    _stateTagName(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SPACE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].TABULATION:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].FORM_FEED:
                {
                    this.state = State.BEFORE_ATTRIBUTE_NAME;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SOLIDUS:
                {
                    this.state = State.SELF_CLOSING_START_TAG;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this.state = State.DATA;
                    this.emitCurrentTagToken();
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    token.tagName += __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"];
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInTag);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    token.tagName += String.fromCodePoint(isAsciiUpper(cp) ? toAsciiLower(cp) : cp);
                }
        }
    }
    // RCDATA less-than sign state
    //------------------------------------------------------------------
    _stateRcdataLessThanSign(cp) {
        if (cp === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SOLIDUS) {
            this.state = State.RCDATA_END_TAG_OPEN;
        } else {
            this._emitChars('<');
            this.state = State.RCDATA;
            this._stateRcdata(cp);
        }
    }
    // RCDATA end tag open state
    //------------------------------------------------------------------
    _stateRcdataEndTagOpen(cp) {
        if (isAsciiLetter(cp)) {
            this.state = State.RCDATA_END_TAG_NAME;
            this._stateRcdataEndTagName(cp);
        } else {
            this._emitChars('</');
            this.state = State.RCDATA;
            this._stateRcdata(cp);
        }
    }
    handleSpecialEndTag(_cp) {
        if (!this.preprocessor.startsWith(this.lastStartTagName, false)) {
            return !this._ensureHibernation();
        }
        this._createEndTagToken();
        const token = this.currentToken;
        token.tagName = this.lastStartTagName;
        const cp = this.preprocessor.peek(this.lastStartTagName.length);
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SPACE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].TABULATION:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].FORM_FEED:
                {
                    this._advanceBy(this.lastStartTagName.length);
                    this.state = State.BEFORE_ATTRIBUTE_NAME;
                    return false;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SOLIDUS:
                {
                    this._advanceBy(this.lastStartTagName.length);
                    this.state = State.SELF_CLOSING_START_TAG;
                    return false;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this._advanceBy(this.lastStartTagName.length);
                    this.emitCurrentTagToken();
                    this.state = State.DATA;
                    return false;
                }
            default:
                {
                    return !this._ensureHibernation();
                }
        }
    }
    // RCDATA end tag name state
    //------------------------------------------------------------------
    _stateRcdataEndTagName(cp) {
        if (this.handleSpecialEndTag(cp)) {
            this._emitChars('</');
            this.state = State.RCDATA;
            this._stateRcdata(cp);
        }
    }
    // RAWTEXT less-than sign state
    //------------------------------------------------------------------
    _stateRawtextLessThanSign(cp) {
        if (cp === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SOLIDUS) {
            this.state = State.RAWTEXT_END_TAG_OPEN;
        } else {
            this._emitChars('<');
            this.state = State.RAWTEXT;
            this._stateRawtext(cp);
        }
    }
    // RAWTEXT end tag open state
    //------------------------------------------------------------------
    _stateRawtextEndTagOpen(cp) {
        if (isAsciiLetter(cp)) {
            this.state = State.RAWTEXT_END_TAG_NAME;
            this._stateRawtextEndTagName(cp);
        } else {
            this._emitChars('</');
            this.state = State.RAWTEXT;
            this._stateRawtext(cp);
        }
    }
    // RAWTEXT end tag name state
    //------------------------------------------------------------------
    _stateRawtextEndTagName(cp) {
        if (this.handleSpecialEndTag(cp)) {
            this._emitChars('</');
            this.state = State.RAWTEXT;
            this._stateRawtext(cp);
        }
    }
    // Script data less-than sign state
    //------------------------------------------------------------------
    _stateScriptDataLessThanSign(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SOLIDUS:
                {
                    this.state = State.SCRIPT_DATA_END_TAG_OPEN;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EXCLAMATION_MARK:
                {
                    this.state = State.SCRIPT_DATA_ESCAPE_START;
                    this._emitChars('<!');
                    break;
                }
            default:
                {
                    this._emitChars('<');
                    this.state = State.SCRIPT_DATA;
                    this._stateScriptData(cp);
                }
        }
    }
    // Script data end tag open state
    //------------------------------------------------------------------
    _stateScriptDataEndTagOpen(cp) {
        if (isAsciiLetter(cp)) {
            this.state = State.SCRIPT_DATA_END_TAG_NAME;
            this._stateScriptDataEndTagName(cp);
        } else {
            this._emitChars('</');
            this.state = State.SCRIPT_DATA;
            this._stateScriptData(cp);
        }
    }
    // Script data end tag name state
    //------------------------------------------------------------------
    _stateScriptDataEndTagName(cp) {
        if (this.handleSpecialEndTag(cp)) {
            this._emitChars('</');
            this.state = State.SCRIPT_DATA;
            this._stateScriptData(cp);
        }
    }
    // Script data escape start state
    //------------------------------------------------------------------
    _stateScriptDataEscapeStart(cp) {
        if (cp === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].HYPHEN_MINUS) {
            this.state = State.SCRIPT_DATA_ESCAPE_START_DASH;
            this._emitChars('-');
        } else {
            this.state = State.SCRIPT_DATA;
            this._stateScriptData(cp);
        }
    }
    // Script data escape start dash state
    //------------------------------------------------------------------
    _stateScriptDataEscapeStartDash(cp) {
        if (cp === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].HYPHEN_MINUS) {
            this.state = State.SCRIPT_DATA_ESCAPED_DASH_DASH;
            this._emitChars('-');
        } else {
            this.state = State.SCRIPT_DATA;
            this._stateScriptData(cp);
        }
    }
    // Script data escaped state
    //------------------------------------------------------------------
    _stateScriptDataEscaped(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].HYPHEN_MINUS:
                {
                    this.state = State.SCRIPT_DATA_ESCAPED_DASH;
                    this._emitChars('-');
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LESS_THAN_SIGN:
                {
                    this.state = State.SCRIPT_DATA_ESCAPED_LESS_THAN_SIGN;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    this._emitChars(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"]);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInScriptHtmlCommentLikeText);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._emitCodePoint(cp);
                }
        }
    }
    // Script data escaped dash state
    //------------------------------------------------------------------
    _stateScriptDataEscapedDash(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].HYPHEN_MINUS:
                {
                    this.state = State.SCRIPT_DATA_ESCAPED_DASH_DASH;
                    this._emitChars('-');
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LESS_THAN_SIGN:
                {
                    this.state = State.SCRIPT_DATA_ESCAPED_LESS_THAN_SIGN;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    this.state = State.SCRIPT_DATA_ESCAPED;
                    this._emitChars(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"]);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInScriptHtmlCommentLikeText);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this.state = State.SCRIPT_DATA_ESCAPED;
                    this._emitCodePoint(cp);
                }
        }
    }
    // Script data escaped dash dash state
    //------------------------------------------------------------------
    _stateScriptDataEscapedDashDash(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].HYPHEN_MINUS:
                {
                    this._emitChars('-');
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LESS_THAN_SIGN:
                {
                    this.state = State.SCRIPT_DATA_ESCAPED_LESS_THAN_SIGN;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this.state = State.SCRIPT_DATA;
                    this._emitChars('>');
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    this.state = State.SCRIPT_DATA_ESCAPED;
                    this._emitChars(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"]);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInScriptHtmlCommentLikeText);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this.state = State.SCRIPT_DATA_ESCAPED;
                    this._emitCodePoint(cp);
                }
        }
    }
    // Script data escaped less-than sign state
    //------------------------------------------------------------------
    _stateScriptDataEscapedLessThanSign(cp) {
        if (cp === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SOLIDUS) {
            this.state = State.SCRIPT_DATA_ESCAPED_END_TAG_OPEN;
        } else if (isAsciiLetter(cp)) {
            this._emitChars('<');
            this.state = State.SCRIPT_DATA_DOUBLE_ESCAPE_START;
            this._stateScriptDataDoubleEscapeStart(cp);
        } else {
            this._emitChars('<');
            this.state = State.SCRIPT_DATA_ESCAPED;
            this._stateScriptDataEscaped(cp);
        }
    }
    // Script data escaped end tag open state
    //------------------------------------------------------------------
    _stateScriptDataEscapedEndTagOpen(cp) {
        if (isAsciiLetter(cp)) {
            this.state = State.SCRIPT_DATA_ESCAPED_END_TAG_NAME;
            this._stateScriptDataEscapedEndTagName(cp);
        } else {
            this._emitChars('</');
            this.state = State.SCRIPT_DATA_ESCAPED;
            this._stateScriptDataEscaped(cp);
        }
    }
    // Script data escaped end tag name state
    //------------------------------------------------------------------
    _stateScriptDataEscapedEndTagName(cp) {
        if (this.handleSpecialEndTag(cp)) {
            this._emitChars('</');
            this.state = State.SCRIPT_DATA_ESCAPED;
            this._stateScriptDataEscaped(cp);
        }
    }
    // Script data double escape start state
    //------------------------------------------------------------------
    _stateScriptDataDoubleEscapeStart(cp) {
        if (this.preprocessor.startsWith(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SEQUENCES"].SCRIPT, false) && isScriptDataDoubleEscapeSequenceEnd(this.preprocessor.peek(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SEQUENCES"].SCRIPT.length))) {
            this._emitCodePoint(cp);
            for(let i = 0; i < __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SEQUENCES"].SCRIPT.length; i++){
                this._emitCodePoint(this._consume());
            }
            this.state = State.SCRIPT_DATA_DOUBLE_ESCAPED;
        } else if (!this._ensureHibernation()) {
            this.state = State.SCRIPT_DATA_ESCAPED;
            this._stateScriptDataEscaped(cp);
        }
    }
    // Script data double escaped state
    //------------------------------------------------------------------
    _stateScriptDataDoubleEscaped(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].HYPHEN_MINUS:
                {
                    this.state = State.SCRIPT_DATA_DOUBLE_ESCAPED_DASH;
                    this._emitChars('-');
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LESS_THAN_SIGN:
                {
                    this.state = State.SCRIPT_DATA_DOUBLE_ESCAPED_LESS_THAN_SIGN;
                    this._emitChars('<');
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    this._emitChars(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"]);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInScriptHtmlCommentLikeText);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._emitCodePoint(cp);
                }
        }
    }
    // Script data double escaped dash state
    //------------------------------------------------------------------
    _stateScriptDataDoubleEscapedDash(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].HYPHEN_MINUS:
                {
                    this.state = State.SCRIPT_DATA_DOUBLE_ESCAPED_DASH_DASH;
                    this._emitChars('-');
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LESS_THAN_SIGN:
                {
                    this.state = State.SCRIPT_DATA_DOUBLE_ESCAPED_LESS_THAN_SIGN;
                    this._emitChars('<');
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    this.state = State.SCRIPT_DATA_DOUBLE_ESCAPED;
                    this._emitChars(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"]);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInScriptHtmlCommentLikeText);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this.state = State.SCRIPT_DATA_DOUBLE_ESCAPED;
                    this._emitCodePoint(cp);
                }
        }
    }
    // Script data double escaped dash dash state
    //------------------------------------------------------------------
    _stateScriptDataDoubleEscapedDashDash(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].HYPHEN_MINUS:
                {
                    this._emitChars('-');
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LESS_THAN_SIGN:
                {
                    this.state = State.SCRIPT_DATA_DOUBLE_ESCAPED_LESS_THAN_SIGN;
                    this._emitChars('<');
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this.state = State.SCRIPT_DATA;
                    this._emitChars('>');
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    this.state = State.SCRIPT_DATA_DOUBLE_ESCAPED;
                    this._emitChars(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"]);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInScriptHtmlCommentLikeText);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this.state = State.SCRIPT_DATA_DOUBLE_ESCAPED;
                    this._emitCodePoint(cp);
                }
        }
    }
    // Script data double escaped less-than sign state
    //------------------------------------------------------------------
    _stateScriptDataDoubleEscapedLessThanSign(cp) {
        if (cp === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SOLIDUS) {
            this.state = State.SCRIPT_DATA_DOUBLE_ESCAPE_END;
            this._emitChars('/');
        } else {
            this.state = State.SCRIPT_DATA_DOUBLE_ESCAPED;
            this._stateScriptDataDoubleEscaped(cp);
        }
    }
    // Script data double escape end state
    //------------------------------------------------------------------
    _stateScriptDataDoubleEscapeEnd(cp) {
        if (this.preprocessor.startsWith(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SEQUENCES"].SCRIPT, false) && isScriptDataDoubleEscapeSequenceEnd(this.preprocessor.peek(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SEQUENCES"].SCRIPT.length))) {
            this._emitCodePoint(cp);
            for(let i = 0; i < __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SEQUENCES"].SCRIPT.length; i++){
                this._emitCodePoint(this._consume());
            }
            this.state = State.SCRIPT_DATA_ESCAPED;
        } else if (!this._ensureHibernation()) {
            this.state = State.SCRIPT_DATA_DOUBLE_ESCAPED;
            this._stateScriptDataDoubleEscaped(cp);
        }
    }
    // Before attribute name state
    //------------------------------------------------------------------
    _stateBeforeAttributeName(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SPACE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].TABULATION:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].FORM_FEED:
                {
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SOLIDUS:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this.state = State.AFTER_ATTRIBUTE_NAME;
                    this._stateAfterAttributeName(cp);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EQUALS_SIGN:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedEqualsSignBeforeAttributeName);
                    this._createAttr('=');
                    this.state = State.ATTRIBUTE_NAME;
                    break;
                }
            default:
                {
                    this._createAttr('');
                    this.state = State.ATTRIBUTE_NAME;
                    this._stateAttributeName(cp);
                }
        }
    }
    // Attribute name state
    //------------------------------------------------------------------
    _stateAttributeName(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SPACE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].TABULATION:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].FORM_FEED:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SOLIDUS:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._leaveAttrName();
                    this.state = State.AFTER_ATTRIBUTE_NAME;
                    this._stateAfterAttributeName(cp);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EQUALS_SIGN:
                {
                    this._leaveAttrName();
                    this.state = State.BEFORE_ATTRIBUTE_VALUE;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].QUOTATION_MARK:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].APOSTROPHE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LESS_THAN_SIGN:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedCharacterInAttributeName);
                    this.currentAttr.name += String.fromCodePoint(cp);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    this.currentAttr.name += __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"];
                    break;
                }
            default:
                {
                    this.currentAttr.name += String.fromCodePoint(isAsciiUpper(cp) ? toAsciiLower(cp) : cp);
                }
        }
    }
    // After attribute name state
    //------------------------------------------------------------------
    _stateAfterAttributeName(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SPACE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].TABULATION:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].FORM_FEED:
                {
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SOLIDUS:
                {
                    this.state = State.SELF_CLOSING_START_TAG;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EQUALS_SIGN:
                {
                    this.state = State.BEFORE_ATTRIBUTE_VALUE;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this.state = State.DATA;
                    this.emitCurrentTagToken();
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInTag);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._createAttr('');
                    this.state = State.ATTRIBUTE_NAME;
                    this._stateAttributeName(cp);
                }
        }
    }
    // Before attribute value state
    //------------------------------------------------------------------
    _stateBeforeAttributeValue(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SPACE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].TABULATION:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].FORM_FEED:
                {
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].QUOTATION_MARK:
                {
                    this.state = State.ATTRIBUTE_VALUE_DOUBLE_QUOTED;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].APOSTROPHE:
                {
                    this.state = State.ATTRIBUTE_VALUE_SINGLE_QUOTED;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingAttributeValue);
                    this.state = State.DATA;
                    this.emitCurrentTagToken();
                    break;
                }
            default:
                {
                    this.state = State.ATTRIBUTE_VALUE_UNQUOTED;
                    this._stateAttributeValueUnquoted(cp);
                }
        }
    }
    // Attribute value (double-quoted) state
    //------------------------------------------------------------------
    _stateAttributeValueDoubleQuoted(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].QUOTATION_MARK:
                {
                    this.state = State.AFTER_ATTRIBUTE_VALUE_QUOTED;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].AMPERSAND:
                {
                    this._startCharacterReference();
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    this.currentAttr.value += __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"];
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInTag);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this.currentAttr.value += String.fromCodePoint(cp);
                }
        }
    }
    // Attribute value (single-quoted) state
    //------------------------------------------------------------------
    _stateAttributeValueSingleQuoted(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].APOSTROPHE:
                {
                    this.state = State.AFTER_ATTRIBUTE_VALUE_QUOTED;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].AMPERSAND:
                {
                    this._startCharacterReference();
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    this.currentAttr.value += __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"];
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInTag);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this.currentAttr.value += String.fromCodePoint(cp);
                }
        }
    }
    // Attribute value (unquoted) state
    //------------------------------------------------------------------
    _stateAttributeValueUnquoted(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SPACE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].TABULATION:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].FORM_FEED:
                {
                    this._leaveAttrValue();
                    this.state = State.BEFORE_ATTRIBUTE_NAME;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].AMPERSAND:
                {
                    this._startCharacterReference();
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this._leaveAttrValue();
                    this.state = State.DATA;
                    this.emitCurrentTagToken();
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    this.currentAttr.value += __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"];
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].QUOTATION_MARK:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].APOSTROPHE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LESS_THAN_SIGN:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EQUALS_SIGN:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GRAVE_ACCENT:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedCharacterInUnquotedAttributeValue);
                    this.currentAttr.value += String.fromCodePoint(cp);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInTag);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this.currentAttr.value += String.fromCodePoint(cp);
                }
        }
    }
    // After attribute value (quoted) state
    //------------------------------------------------------------------
    _stateAfterAttributeValueQuoted(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SPACE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].TABULATION:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].FORM_FEED:
                {
                    this._leaveAttrValue();
                    this.state = State.BEFORE_ATTRIBUTE_NAME;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SOLIDUS:
                {
                    this._leaveAttrValue();
                    this.state = State.SELF_CLOSING_START_TAG;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this._leaveAttrValue();
                    this.state = State.DATA;
                    this.emitCurrentTagToken();
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInTag);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingWhitespaceBetweenAttributes);
                    this.state = State.BEFORE_ATTRIBUTE_NAME;
                    this._stateBeforeAttributeName(cp);
                }
        }
    }
    // Self-closing start tag state
    //------------------------------------------------------------------
    _stateSelfClosingStartTag(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    const token = this.currentToken;
                    token.selfClosing = true;
                    this.state = State.DATA;
                    this.emitCurrentTagToken();
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInTag);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedSolidusInTag);
                    this.state = State.BEFORE_ATTRIBUTE_NAME;
                    this._stateBeforeAttributeName(cp);
                }
        }
    }
    // Bogus comment state
    //------------------------------------------------------------------
    _stateBogusComment(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this.state = State.DATA;
                    this.emitCurrentComment(token);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this.emitCurrentComment(token);
                    this._emitEOFToken();
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    token.data += __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"];
                    break;
                }
            default:
                {
                    token.data += String.fromCodePoint(cp);
                }
        }
    }
    // Markup declaration open state
    //------------------------------------------------------------------
    _stateMarkupDeclarationOpen(cp) {
        if (this._consumeSequenceIfMatch(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SEQUENCES"].DASH_DASH, true)) {
            this._createCommentToken(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SEQUENCES"].DASH_DASH.length + 1);
            this.state = State.COMMENT_START;
        } else if (this._consumeSequenceIfMatch(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SEQUENCES"].DOCTYPE, false)) {
            // NOTE: Doctypes tokens are created without fixed offsets. We keep track of the moment a doctype *might* start here.
            this.currentLocation = this.getCurrentLocation(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SEQUENCES"].DOCTYPE.length + 1);
            this.state = State.DOCTYPE;
        } else if (this._consumeSequenceIfMatch(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SEQUENCES"].CDATA_START, true)) {
            if (this.inForeignNode) {
                this.state = State.CDATA_SECTION;
            } else {
                this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].cdataInHtmlContent);
                this._createCommentToken(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SEQUENCES"].CDATA_START.length + 1);
                this.currentToken.data = '[CDATA[';
                this.state = State.BOGUS_COMMENT;
            }
        } else if (!this._ensureHibernation()) {
            this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].incorrectlyOpenedComment);
            this._createCommentToken(2);
            this.state = State.BOGUS_COMMENT;
            this._stateBogusComment(cp);
        }
    }
    // Comment start state
    //------------------------------------------------------------------
    _stateCommentStart(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].HYPHEN_MINUS:
                {
                    this.state = State.COMMENT_START_DASH;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].abruptClosingOfEmptyComment);
                    this.state = State.DATA;
                    const token = this.currentToken;
                    this.emitCurrentComment(token);
                    break;
                }
            default:
                {
                    this.state = State.COMMENT;
                    this._stateComment(cp);
                }
        }
    }
    // Comment start dash state
    //------------------------------------------------------------------
    _stateCommentStartDash(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].HYPHEN_MINUS:
                {
                    this.state = State.COMMENT_END;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].abruptClosingOfEmptyComment);
                    this.state = State.DATA;
                    this.emitCurrentComment(token);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInComment);
                    this.emitCurrentComment(token);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    token.data += '-';
                    this.state = State.COMMENT;
                    this._stateComment(cp);
                }
        }
    }
    // Comment state
    //------------------------------------------------------------------
    _stateComment(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].HYPHEN_MINUS:
                {
                    this.state = State.COMMENT_END_DASH;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LESS_THAN_SIGN:
                {
                    token.data += '<';
                    this.state = State.COMMENT_LESS_THAN_SIGN;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    token.data += __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"];
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInComment);
                    this.emitCurrentComment(token);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    token.data += String.fromCodePoint(cp);
                }
        }
    }
    // Comment less-than sign state
    //------------------------------------------------------------------
    _stateCommentLessThanSign(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EXCLAMATION_MARK:
                {
                    token.data += '!';
                    this.state = State.COMMENT_LESS_THAN_SIGN_BANG;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LESS_THAN_SIGN:
                {
                    token.data += '<';
                    break;
                }
            default:
                {
                    this.state = State.COMMENT;
                    this._stateComment(cp);
                }
        }
    }
    // Comment less-than sign bang state
    //------------------------------------------------------------------
    _stateCommentLessThanSignBang(cp) {
        if (cp === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].HYPHEN_MINUS) {
            this.state = State.COMMENT_LESS_THAN_SIGN_BANG_DASH;
        } else {
            this.state = State.COMMENT;
            this._stateComment(cp);
        }
    }
    // Comment less-than sign bang dash state
    //------------------------------------------------------------------
    _stateCommentLessThanSignBangDash(cp) {
        if (cp === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].HYPHEN_MINUS) {
            this.state = State.COMMENT_LESS_THAN_SIGN_BANG_DASH_DASH;
        } else {
            this.state = State.COMMENT_END_DASH;
            this._stateCommentEndDash(cp);
        }
    }
    // Comment less-than sign bang dash dash state
    //------------------------------------------------------------------
    _stateCommentLessThanSignBangDashDash(cp) {
        if (cp !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN && cp !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF) {
            this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].nestedComment);
        }
        this.state = State.COMMENT_END;
        this._stateCommentEnd(cp);
    }
    // Comment end dash state
    //------------------------------------------------------------------
    _stateCommentEndDash(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].HYPHEN_MINUS:
                {
                    this.state = State.COMMENT_END;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInComment);
                    this.emitCurrentComment(token);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    token.data += '-';
                    this.state = State.COMMENT;
                    this._stateComment(cp);
                }
        }
    }
    // Comment end state
    //------------------------------------------------------------------
    _stateCommentEnd(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this.state = State.DATA;
                    this.emitCurrentComment(token);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EXCLAMATION_MARK:
                {
                    this.state = State.COMMENT_END_BANG;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].HYPHEN_MINUS:
                {
                    token.data += '-';
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInComment);
                    this.emitCurrentComment(token);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    token.data += '--';
                    this.state = State.COMMENT;
                    this._stateComment(cp);
                }
        }
    }
    // Comment end bang state
    //------------------------------------------------------------------
    _stateCommentEndBang(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].HYPHEN_MINUS:
                {
                    token.data += '--!';
                    this.state = State.COMMENT_END_DASH;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].incorrectlyClosedComment);
                    this.state = State.DATA;
                    this.emitCurrentComment(token);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInComment);
                    this.emitCurrentComment(token);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    token.data += '--!';
                    this.state = State.COMMENT;
                    this._stateComment(cp);
                }
        }
    }
    // DOCTYPE state
    //------------------------------------------------------------------
    _stateDoctype(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SPACE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].TABULATION:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].FORM_FEED:
                {
                    this.state = State.BEFORE_DOCTYPE_NAME;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this.state = State.BEFORE_DOCTYPE_NAME;
                    this._stateBeforeDoctypeName(cp);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInDoctype);
                    this._createDoctypeToken(null);
                    const token = this.currentToken;
                    token.forceQuirks = true;
                    this.emitCurrentDoctype(token);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingWhitespaceBeforeDoctypeName);
                    this.state = State.BEFORE_DOCTYPE_NAME;
                    this._stateBeforeDoctypeName(cp);
                }
        }
    }
    // Before DOCTYPE name state
    //------------------------------------------------------------------
    _stateBeforeDoctypeName(cp) {
        if (isAsciiUpper(cp)) {
            this._createDoctypeToken(String.fromCharCode(toAsciiLower(cp)));
            this.state = State.DOCTYPE_NAME;
        } else switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SPACE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].TABULATION:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].FORM_FEED:
                {
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    this._createDoctypeToken(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"]);
                    this.state = State.DOCTYPE_NAME;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingDoctypeName);
                    this._createDoctypeToken(null);
                    const token = this.currentToken;
                    token.forceQuirks = true;
                    this.emitCurrentDoctype(token);
                    this.state = State.DATA;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInDoctype);
                    this._createDoctypeToken(null);
                    const token = this.currentToken;
                    token.forceQuirks = true;
                    this.emitCurrentDoctype(token);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._createDoctypeToken(String.fromCodePoint(cp));
                    this.state = State.DOCTYPE_NAME;
                }
        }
    }
    // DOCTYPE name state
    //------------------------------------------------------------------
    _stateDoctypeName(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SPACE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].TABULATION:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].FORM_FEED:
                {
                    this.state = State.AFTER_DOCTYPE_NAME;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this.state = State.DATA;
                    this.emitCurrentDoctype(token);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    token.name += __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"];
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInDoctype);
                    token.forceQuirks = true;
                    this.emitCurrentDoctype(token);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    token.name += String.fromCodePoint(isAsciiUpper(cp) ? toAsciiLower(cp) : cp);
                }
        }
    }
    // After DOCTYPE name state
    //------------------------------------------------------------------
    _stateAfterDoctypeName(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SPACE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].TABULATION:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].FORM_FEED:
                {
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this.state = State.DATA;
                    this.emitCurrentDoctype(token);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInDoctype);
                    token.forceQuirks = true;
                    this.emitCurrentDoctype(token);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    if (this._consumeSequenceIfMatch(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SEQUENCES"].PUBLIC, false)) {
                        this.state = State.AFTER_DOCTYPE_PUBLIC_KEYWORD;
                    } else if (this._consumeSequenceIfMatch(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SEQUENCES"].SYSTEM, false)) {
                        this.state = State.AFTER_DOCTYPE_SYSTEM_KEYWORD;
                    } else if (!this._ensureHibernation()) {
                        this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].invalidCharacterSequenceAfterDoctypeName);
                        token.forceQuirks = true;
                        this.state = State.BOGUS_DOCTYPE;
                        this._stateBogusDoctype(cp);
                    }
                }
        }
    }
    // After DOCTYPE public keyword state
    //------------------------------------------------------------------
    _stateAfterDoctypePublicKeyword(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SPACE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].TABULATION:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].FORM_FEED:
                {
                    this.state = State.BEFORE_DOCTYPE_PUBLIC_IDENTIFIER;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].QUOTATION_MARK:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingWhitespaceAfterDoctypePublicKeyword);
                    token.publicId = '';
                    this.state = State.DOCTYPE_PUBLIC_IDENTIFIER_DOUBLE_QUOTED;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].APOSTROPHE:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingWhitespaceAfterDoctypePublicKeyword);
                    token.publicId = '';
                    this.state = State.DOCTYPE_PUBLIC_IDENTIFIER_SINGLE_QUOTED;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingDoctypePublicIdentifier);
                    token.forceQuirks = true;
                    this.state = State.DATA;
                    this.emitCurrentDoctype(token);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInDoctype);
                    token.forceQuirks = true;
                    this.emitCurrentDoctype(token);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingQuoteBeforeDoctypePublicIdentifier);
                    token.forceQuirks = true;
                    this.state = State.BOGUS_DOCTYPE;
                    this._stateBogusDoctype(cp);
                }
        }
    }
    // Before DOCTYPE public identifier state
    //------------------------------------------------------------------
    _stateBeforeDoctypePublicIdentifier(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SPACE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].TABULATION:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].FORM_FEED:
                {
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].QUOTATION_MARK:
                {
                    token.publicId = '';
                    this.state = State.DOCTYPE_PUBLIC_IDENTIFIER_DOUBLE_QUOTED;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].APOSTROPHE:
                {
                    token.publicId = '';
                    this.state = State.DOCTYPE_PUBLIC_IDENTIFIER_SINGLE_QUOTED;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingDoctypePublicIdentifier);
                    token.forceQuirks = true;
                    this.state = State.DATA;
                    this.emitCurrentDoctype(token);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInDoctype);
                    token.forceQuirks = true;
                    this.emitCurrentDoctype(token);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingQuoteBeforeDoctypePublicIdentifier);
                    token.forceQuirks = true;
                    this.state = State.BOGUS_DOCTYPE;
                    this._stateBogusDoctype(cp);
                }
        }
    }
    // DOCTYPE public identifier (double-quoted) state
    //------------------------------------------------------------------
    _stateDoctypePublicIdentifierDoubleQuoted(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].QUOTATION_MARK:
                {
                    this.state = State.AFTER_DOCTYPE_PUBLIC_IDENTIFIER;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    token.publicId += __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"];
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].abruptDoctypePublicIdentifier);
                    token.forceQuirks = true;
                    this.emitCurrentDoctype(token);
                    this.state = State.DATA;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInDoctype);
                    token.forceQuirks = true;
                    this.emitCurrentDoctype(token);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    token.publicId += String.fromCodePoint(cp);
                }
        }
    }
    // DOCTYPE public identifier (single-quoted) state
    //------------------------------------------------------------------
    _stateDoctypePublicIdentifierSingleQuoted(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].APOSTROPHE:
                {
                    this.state = State.AFTER_DOCTYPE_PUBLIC_IDENTIFIER;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    token.publicId += __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"];
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].abruptDoctypePublicIdentifier);
                    token.forceQuirks = true;
                    this.emitCurrentDoctype(token);
                    this.state = State.DATA;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInDoctype);
                    token.forceQuirks = true;
                    this.emitCurrentDoctype(token);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    token.publicId += String.fromCodePoint(cp);
                }
        }
    }
    // After DOCTYPE public identifier state
    //------------------------------------------------------------------
    _stateAfterDoctypePublicIdentifier(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SPACE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].TABULATION:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].FORM_FEED:
                {
                    this.state = State.BETWEEN_DOCTYPE_PUBLIC_AND_SYSTEM_IDENTIFIERS;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this.state = State.DATA;
                    this.emitCurrentDoctype(token);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].QUOTATION_MARK:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingWhitespaceBetweenDoctypePublicAndSystemIdentifiers);
                    token.systemId = '';
                    this.state = State.DOCTYPE_SYSTEM_IDENTIFIER_DOUBLE_QUOTED;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].APOSTROPHE:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingWhitespaceBetweenDoctypePublicAndSystemIdentifiers);
                    token.systemId = '';
                    this.state = State.DOCTYPE_SYSTEM_IDENTIFIER_SINGLE_QUOTED;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInDoctype);
                    token.forceQuirks = true;
                    this.emitCurrentDoctype(token);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingQuoteBeforeDoctypeSystemIdentifier);
                    token.forceQuirks = true;
                    this.state = State.BOGUS_DOCTYPE;
                    this._stateBogusDoctype(cp);
                }
        }
    }
    // Between DOCTYPE public and system identifiers state
    //------------------------------------------------------------------
    _stateBetweenDoctypePublicAndSystemIdentifiers(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SPACE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].TABULATION:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].FORM_FEED:
                {
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this.emitCurrentDoctype(token);
                    this.state = State.DATA;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].QUOTATION_MARK:
                {
                    token.systemId = '';
                    this.state = State.DOCTYPE_SYSTEM_IDENTIFIER_DOUBLE_QUOTED;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].APOSTROPHE:
                {
                    token.systemId = '';
                    this.state = State.DOCTYPE_SYSTEM_IDENTIFIER_SINGLE_QUOTED;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInDoctype);
                    token.forceQuirks = true;
                    this.emitCurrentDoctype(token);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingQuoteBeforeDoctypeSystemIdentifier);
                    token.forceQuirks = true;
                    this.state = State.BOGUS_DOCTYPE;
                    this._stateBogusDoctype(cp);
                }
        }
    }
    // After DOCTYPE system keyword state
    //------------------------------------------------------------------
    _stateAfterDoctypeSystemKeyword(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SPACE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].TABULATION:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].FORM_FEED:
                {
                    this.state = State.BEFORE_DOCTYPE_SYSTEM_IDENTIFIER;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].QUOTATION_MARK:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingWhitespaceAfterDoctypeSystemKeyword);
                    token.systemId = '';
                    this.state = State.DOCTYPE_SYSTEM_IDENTIFIER_DOUBLE_QUOTED;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].APOSTROPHE:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingWhitespaceAfterDoctypeSystemKeyword);
                    token.systemId = '';
                    this.state = State.DOCTYPE_SYSTEM_IDENTIFIER_SINGLE_QUOTED;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingDoctypeSystemIdentifier);
                    token.forceQuirks = true;
                    this.state = State.DATA;
                    this.emitCurrentDoctype(token);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInDoctype);
                    token.forceQuirks = true;
                    this.emitCurrentDoctype(token);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingQuoteBeforeDoctypeSystemIdentifier);
                    token.forceQuirks = true;
                    this.state = State.BOGUS_DOCTYPE;
                    this._stateBogusDoctype(cp);
                }
        }
    }
    // Before DOCTYPE system identifier state
    //------------------------------------------------------------------
    _stateBeforeDoctypeSystemIdentifier(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SPACE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].TABULATION:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].FORM_FEED:
                {
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].QUOTATION_MARK:
                {
                    token.systemId = '';
                    this.state = State.DOCTYPE_SYSTEM_IDENTIFIER_DOUBLE_QUOTED;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].APOSTROPHE:
                {
                    token.systemId = '';
                    this.state = State.DOCTYPE_SYSTEM_IDENTIFIER_SINGLE_QUOTED;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingDoctypeSystemIdentifier);
                    token.forceQuirks = true;
                    this.state = State.DATA;
                    this.emitCurrentDoctype(token);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInDoctype);
                    token.forceQuirks = true;
                    this.emitCurrentDoctype(token);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingQuoteBeforeDoctypeSystemIdentifier);
                    token.forceQuirks = true;
                    this.state = State.BOGUS_DOCTYPE;
                    this._stateBogusDoctype(cp);
                }
        }
    }
    // DOCTYPE system identifier (double-quoted) state
    //------------------------------------------------------------------
    _stateDoctypeSystemIdentifierDoubleQuoted(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].QUOTATION_MARK:
                {
                    this.state = State.AFTER_DOCTYPE_SYSTEM_IDENTIFIER;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    token.systemId += __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"];
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].abruptDoctypeSystemIdentifier);
                    token.forceQuirks = true;
                    this.emitCurrentDoctype(token);
                    this.state = State.DATA;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInDoctype);
                    token.forceQuirks = true;
                    this.emitCurrentDoctype(token);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    token.systemId += String.fromCodePoint(cp);
                }
        }
    }
    // DOCTYPE system identifier (single-quoted) state
    //------------------------------------------------------------------
    _stateDoctypeSystemIdentifierSingleQuoted(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].APOSTROPHE:
                {
                    this.state = State.AFTER_DOCTYPE_SYSTEM_IDENTIFIER;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    token.systemId += __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"];
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].abruptDoctypeSystemIdentifier);
                    token.forceQuirks = true;
                    this.emitCurrentDoctype(token);
                    this.state = State.DATA;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInDoctype);
                    token.forceQuirks = true;
                    this.emitCurrentDoctype(token);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    token.systemId += String.fromCodePoint(cp);
                }
        }
    }
    // After DOCTYPE system identifier state
    //------------------------------------------------------------------
    _stateAfterDoctypeSystemIdentifier(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SPACE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].TABULATION:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].FORM_FEED:
                {
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this.emitCurrentDoctype(token);
                    this.state = State.DATA;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInDoctype);
                    token.forceQuirks = true;
                    this.emitCurrentDoctype(token);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedCharacterAfterDoctypeSystemIdentifier);
                    this.state = State.BOGUS_DOCTYPE;
                    this._stateBogusDoctype(cp);
                }
        }
    }
    // Bogus DOCTYPE state
    //------------------------------------------------------------------
    _stateBogusDoctype(cp) {
        const token = this.currentToken;
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this.emitCurrentDoctype(token);
                    this.state = State.DATA;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].NULL:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unexpectedNullCharacter);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this.emitCurrentDoctype(token);
                    this._emitEOFToken();
                    break;
                }
            default:
        }
    }
    // CDATA section state
    //------------------------------------------------------------------
    _stateCdataSection(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].RIGHT_SQUARE_BRACKET:
                {
                    this.state = State.CDATA_SECTION_BRACKET;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].EOF:
                {
                    this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInCdata);
                    this._emitEOFToken();
                    break;
                }
            default:
                {
                    this._emitCodePoint(cp);
                }
        }
    }
    // CDATA section bracket state
    //------------------------------------------------------------------
    _stateCdataSectionBracket(cp) {
        if (cp === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].RIGHT_SQUARE_BRACKET) {
            this.state = State.CDATA_SECTION_END;
        } else {
            this._emitChars(']');
            this.state = State.CDATA_SECTION;
            this._stateCdataSection(cp);
        }
    }
    // CDATA section end state
    //------------------------------------------------------------------
    _stateCdataSectionEnd(cp) {
        switch(cp){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].GREATER_THAN_SIGN:
                {
                    this.state = State.DATA;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].RIGHT_SQUARE_BRACKET:
                {
                    this._emitChars(']');
                    break;
                }
            default:
                {
                    this._emitChars(']]');
                    this.state = State.CDATA_SECTION;
                    this._stateCdataSection(cp);
                }
        }
    }
    // Character reference state
    //------------------------------------------------------------------
    _stateCharacterReference() {
        let length = this.entityDecoder.write(this.preprocessor.html, this.preprocessor.pos);
        if (length < 0) {
            if (this.preprocessor.lastChunkWritten) {
                length = this.entityDecoder.end();
            } else {
                // Wait for the rest of the entity.
                this.active = false;
                // Mark the entire buffer as read.
                this.preprocessor.pos = this.preprocessor.html.length - 1;
                this.consumedAfterSnapshot = 0;
                this.preprocessor.endOfChunkHit = true;
                return;
            }
        }
        if (length === 0) {
            // This was not a valid entity. Go back to the beginning, and
            // figure out what to do.
            this.preprocessor.pos = this.entityStartPos;
            this._flushCodePointConsumedAsCharacterReference(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].AMPERSAND);
            this.state = !this._isCharacterReferenceInAttribute() && isAsciiAlphaNumeric(this.preprocessor.peek(1)) ? State.AMBIGUOUS_AMPERSAND : this.returnState;
        } else {
            // We successfully parsed an entity. Switch to the return state.
            this.state = this.returnState;
        }
    }
    // Ambiguos ampersand state
    //------------------------------------------------------------------
    _stateAmbiguousAmpersand(cp) {
        if (isAsciiAlphaNumeric(cp)) {
            this._flushCodePointConsumedAsCharacterReference(cp);
        } else {
            if (cp === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].SEMICOLON) {
                this._err(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].unknownNamedCharacterReference);
            }
            this.state = this.returnState;
            this._callState(cp);
        }
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/parse5/dist/parser/open-element-stack.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "OpenElementStack",
    ()=>OpenElementStack
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/html.js [app-client] (ecmascript)");
;
//Element utils
const IMPLICIT_END_TAG_REQUIRED = new Set([
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DD,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DT,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].LI,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OPTGROUP,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OPTION,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].P,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].RB,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].RP,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].RT,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].RTC
]);
const IMPLICIT_END_TAG_REQUIRED_THOROUGHLY = new Set([
    ...IMPLICIT_END_TAG_REQUIRED,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CAPTION,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COLGROUP,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TBODY,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TD,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TFOOT,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TH,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].THEAD,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR
]);
const SCOPING_ELEMENTS_HTML = new Set([
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].APPLET,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CAPTION,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].MARQUEE,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OBJECT,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TD,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TH
]);
const SCOPING_ELEMENTS_HTML_LIST = new Set([
    ...SCOPING_ELEMENTS_HTML,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OL,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].UL
]);
const SCOPING_ELEMENTS_HTML_BUTTON = new Set([
    ...SCOPING_ELEMENTS_HTML,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BUTTON
]);
const SCOPING_ELEMENTS_MATHML = new Set([
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].ANNOTATION_XML,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].MI,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].MN,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].MO,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].MS,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].MTEXT
]);
const SCOPING_ELEMENTS_SVG = new Set([
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DESC,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FOREIGN_OBJECT,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TITLE
]);
const TABLE_ROW_CONTEXT = new Set([
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML
]);
const TABLE_BODY_CONTEXT = new Set([
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TBODY,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TFOOT,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].THEAD,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML
]);
const TABLE_CONTEXT = new Set([
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML
]);
const TABLE_CELLS = new Set([
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TD,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TH
]);
class OpenElementStack {
    get currentTmplContentOrNode() {
        return this._isInTemplate() ? this.treeAdapter.getTemplateContent(this.current) : this.current;
    }
    constructor(document, treeAdapter, handler){
        this.treeAdapter = treeAdapter;
        this.handler = handler;
        this.items = [];
        this.tagIDs = [];
        this.stackTop = -1;
        this.tmplCount = 0;
        this.currentTagId = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].UNKNOWN;
        this.current = document;
    }
    //Index of element
    _indexOf(element) {
        return this.items.lastIndexOf(element, this.stackTop);
    }
    //Update current element
    _isInTemplate() {
        return this.currentTagId === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE && this.treeAdapter.getNamespaceURI(this.current) === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML;
    }
    _updateCurrentElement() {
        this.current = this.items[this.stackTop];
        this.currentTagId = this.tagIDs[this.stackTop];
    }
    //Mutations
    push(element, tagID) {
        this.stackTop++;
        this.items[this.stackTop] = element;
        this.current = element;
        this.tagIDs[this.stackTop] = tagID;
        this.currentTagId = tagID;
        if (this._isInTemplate()) {
            this.tmplCount++;
        }
        this.handler.onItemPush(element, tagID, true);
    }
    pop() {
        const popped = this.current;
        if (this.tmplCount > 0 && this._isInTemplate()) {
            this.tmplCount--;
        }
        this.stackTop--;
        this._updateCurrentElement();
        this.handler.onItemPop(popped, true);
    }
    replace(oldElement, newElement) {
        const idx = this._indexOf(oldElement);
        this.items[idx] = newElement;
        if (idx === this.stackTop) {
            this.current = newElement;
        }
    }
    insertAfter(referenceElement, newElement, newElementID) {
        const insertionIdx = this._indexOf(referenceElement) + 1;
        this.items.splice(insertionIdx, 0, newElement);
        this.tagIDs.splice(insertionIdx, 0, newElementID);
        this.stackTop++;
        if (insertionIdx === this.stackTop) {
            this._updateCurrentElement();
        }
        if (this.current && this.currentTagId !== undefined) {
            this.handler.onItemPush(this.current, this.currentTagId, insertionIdx === this.stackTop);
        }
    }
    popUntilTagNamePopped(tagName) {
        let targetIdx = this.stackTop + 1;
        do {
            targetIdx = this.tagIDs.lastIndexOf(tagName, targetIdx - 1);
        }while (targetIdx > 0 && this.treeAdapter.getNamespaceURI(this.items[targetIdx]) !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML)
        this.shortenToLength(Math.max(targetIdx, 0));
    }
    shortenToLength(idx) {
        while(this.stackTop >= idx){
            const popped = this.current;
            if (this.tmplCount > 0 && this._isInTemplate()) {
                this.tmplCount -= 1;
            }
            this.stackTop--;
            this._updateCurrentElement();
            this.handler.onItemPop(popped, this.stackTop < idx);
        }
    }
    popUntilElementPopped(element) {
        const idx = this._indexOf(element);
        this.shortenToLength(Math.max(idx, 0));
    }
    popUntilPopped(tagNames, targetNS) {
        const idx = this._indexOfTagNames(tagNames, targetNS);
        this.shortenToLength(Math.max(idx, 0));
    }
    popUntilNumberedHeaderPopped() {
        this.popUntilPopped(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NUMBERED_HEADERS"], __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    }
    popUntilTableCellPopped() {
        this.popUntilPopped(TABLE_CELLS, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    }
    popAllUpToHtmlElement() {
        //NOTE: here we assume that the root <html> element is always first in the open element stack, so
        //we perform this fast stack clean up.
        this.tmplCount = 0;
        this.shortenToLength(1);
    }
    _indexOfTagNames(tagNames, namespace) {
        for(let i = this.stackTop; i >= 0; i--){
            if (tagNames.has(this.tagIDs[i]) && this.treeAdapter.getNamespaceURI(this.items[i]) === namespace) {
                return i;
            }
        }
        return -1;
    }
    clearBackTo(tagNames, targetNS) {
        const idx = this._indexOfTagNames(tagNames, targetNS);
        this.shortenToLength(idx + 1);
    }
    clearBackToTableContext() {
        this.clearBackTo(TABLE_CONTEXT, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    }
    clearBackToTableBodyContext() {
        this.clearBackTo(TABLE_BODY_CONTEXT, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    }
    clearBackToTableRowContext() {
        this.clearBackTo(TABLE_ROW_CONTEXT, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    }
    remove(element) {
        const idx = this._indexOf(element);
        if (idx >= 0) {
            if (idx === this.stackTop) {
                this.pop();
            } else {
                this.items.splice(idx, 1);
                this.tagIDs.splice(idx, 1);
                this.stackTop--;
                this._updateCurrentElement();
                this.handler.onItemPop(element, false);
            }
        }
    }
    //Search
    tryPeekProperlyNestedBodyElement() {
        //Properly nested <body> element (should be second element in stack).
        return this.stackTop >= 1 && this.tagIDs[1] === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BODY ? this.items[1] : null;
    }
    contains(element) {
        return this._indexOf(element) > -1;
    }
    getCommonAncestor(element) {
        const elementIdx = this._indexOf(element) - 1;
        return elementIdx >= 0 ? this.items[elementIdx] : null;
    }
    isRootHtmlElementCurrent() {
        return this.stackTop === 0 && this.tagIDs[0] === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML;
    }
    //Element in scope
    hasInDynamicScope(tagName, htmlScope) {
        for(let i = this.stackTop; i >= 0; i--){
            const tn = this.tagIDs[i];
            switch(this.treeAdapter.getNamespaceURI(this.items[i])){
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML:
                    {
                        if (tn === tagName) return true;
                        if (htmlScope.has(tn)) return false;
                        break;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].SVG:
                    {
                        if (SCOPING_ELEMENTS_SVG.has(tn)) return false;
                        break;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].MATHML:
                    {
                        if (SCOPING_ELEMENTS_MATHML.has(tn)) return false;
                        break;
                    }
            }
        }
        return true;
    }
    hasInScope(tagName) {
        return this.hasInDynamicScope(tagName, SCOPING_ELEMENTS_HTML);
    }
    hasInListItemScope(tagName) {
        return this.hasInDynamicScope(tagName, SCOPING_ELEMENTS_HTML_LIST);
    }
    hasInButtonScope(tagName) {
        return this.hasInDynamicScope(tagName, SCOPING_ELEMENTS_HTML_BUTTON);
    }
    hasNumberedHeaderInScope() {
        for(let i = this.stackTop; i >= 0; i--){
            const tn = this.tagIDs[i];
            switch(this.treeAdapter.getNamespaceURI(this.items[i])){
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML:
                    {
                        if (__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NUMBERED_HEADERS"].has(tn)) return true;
                        if (SCOPING_ELEMENTS_HTML.has(tn)) return false;
                        break;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].SVG:
                    {
                        if (SCOPING_ELEMENTS_SVG.has(tn)) return false;
                        break;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].MATHML:
                    {
                        if (SCOPING_ELEMENTS_MATHML.has(tn)) return false;
                        break;
                    }
            }
        }
        return true;
    }
    hasInTableScope(tagName) {
        for(let i = this.stackTop; i >= 0; i--){
            if (this.treeAdapter.getNamespaceURI(this.items[i]) !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML) {
                continue;
            }
            switch(this.tagIDs[i]){
                case tagName:
                    {
                        return true;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE:
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML:
                    {
                        return false;
                    }
            }
        }
        return true;
    }
    hasTableBodyContextInTableScope() {
        for(let i = this.stackTop; i >= 0; i--){
            if (this.treeAdapter.getNamespaceURI(this.items[i]) !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML) {
                continue;
            }
            switch(this.tagIDs[i]){
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TBODY:
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].THEAD:
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TFOOT:
                    {
                        return true;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE:
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML:
                    {
                        return false;
                    }
            }
        }
        return true;
    }
    hasInSelectScope(tagName) {
        for(let i = this.stackTop; i >= 0; i--){
            if (this.treeAdapter.getNamespaceURI(this.items[i]) !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML) {
                continue;
            }
            switch(this.tagIDs[i]){
                case tagName:
                    {
                        return true;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OPTION:
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OPTGROUP:
                    {
                        break;
                    }
                default:
                    {
                        return false;
                    }
            }
        }
        return true;
    }
    //Implied end tags
    generateImpliedEndTags() {
        while(this.currentTagId !== undefined && IMPLICIT_END_TAG_REQUIRED.has(this.currentTagId)){
            this.pop();
        }
    }
    generateImpliedEndTagsThoroughly() {
        while(this.currentTagId !== undefined && IMPLICIT_END_TAG_REQUIRED_THOROUGHLY.has(this.currentTagId)){
            this.pop();
        }
    }
    generateImpliedEndTagsWithExclusion(exclusionId) {
        while(this.currentTagId !== undefined && this.currentTagId !== exclusionId && IMPLICIT_END_TAG_REQUIRED_THOROUGHLY.has(this.currentTagId)){
            this.pop();
        }
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/parse5/dist/parser/formatting-element-list.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "EntryType",
    ()=>EntryType,
    "FormattingElementList",
    ()=>FormattingElementList
]);
//Const
const NOAH_ARK_CAPACITY = 3;
var EntryType;
(function(EntryType) {
    EntryType[EntryType["Marker"] = 0] = "Marker";
    EntryType[EntryType["Element"] = 1] = "Element";
})(EntryType || (EntryType = {}));
const MARKER = {
    type: EntryType.Marker
};
class FormattingElementList {
    constructor(treeAdapter){
        this.treeAdapter = treeAdapter;
        this.entries = [];
        this.bookmark = null;
    }
    //Noah Ark's condition
    //OPTIMIZATION: at first we try to find possible candidates for exclusion using
    //lightweight heuristics without thorough attributes check.
    _getNoahArkConditionCandidates(newElement, neAttrs) {
        const candidates = [];
        const neAttrsLength = neAttrs.length;
        const neTagName = this.treeAdapter.getTagName(newElement);
        const neNamespaceURI = this.treeAdapter.getNamespaceURI(newElement);
        for(let i = 0; i < this.entries.length; i++){
            const entry = this.entries[i];
            if (entry.type === EntryType.Marker) {
                break;
            }
            const { element } = entry;
            if (this.treeAdapter.getTagName(element) === neTagName && this.treeAdapter.getNamespaceURI(element) === neNamespaceURI) {
                const elementAttrs = this.treeAdapter.getAttrList(element);
                if (elementAttrs.length === neAttrsLength) {
                    candidates.push({
                        idx: i,
                        attrs: elementAttrs
                    });
                }
            }
        }
        return candidates;
    }
    _ensureNoahArkCondition(newElement) {
        if (this.entries.length < NOAH_ARK_CAPACITY) return;
        const neAttrs = this.treeAdapter.getAttrList(newElement);
        const candidates = this._getNoahArkConditionCandidates(newElement, neAttrs);
        if (candidates.length < NOAH_ARK_CAPACITY) return;
        //NOTE: build attrs map for the new element, so we can perform fast lookups
        const neAttrsMap = new Map(neAttrs.map((neAttr)=>[
                neAttr.name,
                neAttr.value
            ]));
        let validCandidates = 0;
        //NOTE: remove bottommost candidates, until Noah's Ark condition will not be met
        for(let i = 0; i < candidates.length; i++){
            const candidate = candidates[i];
            // We know that `candidate.attrs.length === neAttrs.length`
            if (candidate.attrs.every((cAttr)=>neAttrsMap.get(cAttr.name) === cAttr.value)) {
                validCandidates += 1;
                if (validCandidates >= NOAH_ARK_CAPACITY) {
                    this.entries.splice(candidate.idx, 1);
                }
            }
        }
    }
    //Mutations
    insertMarker() {
        this.entries.unshift(MARKER);
    }
    pushElement(element, token) {
        this._ensureNoahArkCondition(element);
        this.entries.unshift({
            type: EntryType.Element,
            element,
            token
        });
    }
    insertElementAfterBookmark(element, token) {
        const bookmarkIdx = this.entries.indexOf(this.bookmark);
        this.entries.splice(bookmarkIdx, 0, {
            type: EntryType.Element,
            element,
            token
        });
    }
    removeEntry(entry) {
        const entryIndex = this.entries.indexOf(entry);
        if (entryIndex !== -1) {
            this.entries.splice(entryIndex, 1);
        }
    }
    /**
     * Clears the list of formatting elements up to the last marker.
     *
     * @see https://html.spec.whatwg.org/multipage/parsing.html#clear-the-list-of-active-formatting-elements-up-to-the-last-marker
     */ clearToLastMarker() {
        const markerIdx = this.entries.indexOf(MARKER);
        if (markerIdx === -1) {
            this.entries.length = 0;
        } else {
            this.entries.splice(0, markerIdx + 1);
        }
    }
    //Search
    getElementEntryInScopeWithTagName(tagName) {
        const entry = this.entries.find((entry)=>entry.type === EntryType.Marker || this.treeAdapter.getTagName(entry.element) === tagName);
        return entry && entry.type === EntryType.Element ? entry : null;
    }
    getElementEntry(element) {
        return this.entries.find((entry)=>entry.type === EntryType.Element && entry.element === element);
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/parse5/dist/tree-adapters/default.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "defaultTreeAdapter",
    ()=>defaultTreeAdapter
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/html.js [app-client] (ecmascript)");
;
const defaultTreeAdapter = {
    //Node construction
    createDocument () {
        return {
            nodeName: '#document',
            mode: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DOCUMENT_MODE"].NO_QUIRKS,
            childNodes: []
        };
    },
    createDocumentFragment () {
        return {
            nodeName: '#document-fragment',
            childNodes: []
        };
    },
    createElement (tagName, namespaceURI, attrs) {
        return {
            nodeName: tagName,
            tagName,
            attrs,
            namespaceURI,
            childNodes: [],
            parentNode: null
        };
    },
    createCommentNode (data) {
        return {
            nodeName: '#comment',
            data,
            parentNode: null
        };
    },
    createTextNode (value) {
        return {
            nodeName: '#text',
            value,
            parentNode: null
        };
    },
    //Tree mutation
    appendChild (parentNode, newNode) {
        parentNode.childNodes.push(newNode);
        newNode.parentNode = parentNode;
    },
    insertBefore (parentNode, newNode, referenceNode) {
        const insertionIdx = parentNode.childNodes.indexOf(referenceNode);
        parentNode.childNodes.splice(insertionIdx, 0, newNode);
        newNode.parentNode = parentNode;
    },
    setTemplateContent (templateElement, contentElement) {
        templateElement.content = contentElement;
    },
    getTemplateContent (templateElement) {
        return templateElement.content;
    },
    setDocumentType (document, name, publicId, systemId) {
        const doctypeNode = document.childNodes.find((node)=>node.nodeName === '#documentType');
        if (doctypeNode) {
            doctypeNode.name = name;
            doctypeNode.publicId = publicId;
            doctypeNode.systemId = systemId;
        } else {
            const node = {
                nodeName: '#documentType',
                name,
                publicId,
                systemId,
                parentNode: null
            };
            defaultTreeAdapter.appendChild(document, node);
        }
    },
    setDocumentMode (document, mode) {
        document.mode = mode;
    },
    getDocumentMode (document) {
        return document.mode;
    },
    detachNode (node) {
        if (node.parentNode) {
            const idx = node.parentNode.childNodes.indexOf(node);
            node.parentNode.childNodes.splice(idx, 1);
            node.parentNode = null;
        }
    },
    insertText (parentNode, text) {
        if (parentNode.childNodes.length > 0) {
            const prevNode = parentNode.childNodes[parentNode.childNodes.length - 1];
            if (defaultTreeAdapter.isTextNode(prevNode)) {
                prevNode.value += text;
                return;
            }
        }
        defaultTreeAdapter.appendChild(parentNode, defaultTreeAdapter.createTextNode(text));
    },
    insertTextBefore (parentNode, text, referenceNode) {
        const prevNode = parentNode.childNodes[parentNode.childNodes.indexOf(referenceNode) - 1];
        if (prevNode && defaultTreeAdapter.isTextNode(prevNode)) {
            prevNode.value += text;
        } else {
            defaultTreeAdapter.insertBefore(parentNode, defaultTreeAdapter.createTextNode(text), referenceNode);
        }
    },
    adoptAttributes (recipient, attrs) {
        const recipientAttrsMap = new Set(recipient.attrs.map((attr)=>attr.name));
        for(let j = 0; j < attrs.length; j++){
            if (!recipientAttrsMap.has(attrs[j].name)) {
                recipient.attrs.push(attrs[j]);
            }
        }
    },
    //Tree traversing
    getFirstChild (node) {
        return node.childNodes[0];
    },
    getChildNodes (node) {
        return node.childNodes;
    },
    getParentNode (node) {
        return node.parentNode;
    },
    getAttrList (element) {
        return element.attrs;
    },
    //Node data
    getTagName (element) {
        return element.tagName;
    },
    getNamespaceURI (element) {
        return element.namespaceURI;
    },
    getTextNodeContent (textNode) {
        return textNode.value;
    },
    getCommentNodeContent (commentNode) {
        return commentNode.data;
    },
    getDocumentTypeNodeName (doctypeNode) {
        return doctypeNode.name;
    },
    getDocumentTypeNodePublicId (doctypeNode) {
        return doctypeNode.publicId;
    },
    getDocumentTypeNodeSystemId (doctypeNode) {
        return doctypeNode.systemId;
    },
    //Node types
    isTextNode (node) {
        return node.nodeName === '#text';
    },
    isCommentNode (node) {
        return node.nodeName === '#comment';
    },
    isDocumentTypeNode (node) {
        return node.nodeName === '#documentType';
    },
    isElementNode (node) {
        return Object.prototype.hasOwnProperty.call(node, 'tagName');
    },
    // Source code location
    setNodeSourceCodeLocation (node, location) {
        node.sourceCodeLocation = location;
    },
    getNodeSourceCodeLocation (node) {
        return node.sourceCodeLocation;
    },
    updateNodeSourceCodeLocation (node, endLocation) {
        node.sourceCodeLocation = {
            ...node.sourceCodeLocation,
            ...endLocation
        };
    }
};
}),
"[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/doctype.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getDocumentMode",
    ()=>getDocumentMode,
    "isConforming",
    ()=>isConforming
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/html.js [app-client] (ecmascript)");
;
//Const
const VALID_DOCTYPE_NAME = 'html';
const VALID_SYSTEM_ID = 'about:legacy-compat';
const QUIRKS_MODE_SYSTEM_ID = 'http://www.ibm.com/data/dtd/v11/ibmxhtml1-transitional.dtd';
const QUIRKS_MODE_PUBLIC_ID_PREFIXES = [
    '+//silmaril//dtd html pro v0r11 19970101//',
    '-//as//dtd html 3.0 aswedit + extensions//',
    '-//advasoft ltd//dtd html 3.0 aswedit + extensions//',
    '-//ietf//dtd html 2.0 level 1//',
    '-//ietf//dtd html 2.0 level 2//',
    '-//ietf//dtd html 2.0 strict level 1//',
    '-//ietf//dtd html 2.0 strict level 2//',
    '-//ietf//dtd html 2.0 strict//',
    '-//ietf//dtd html 2.0//',
    '-//ietf//dtd html 2.1e//',
    '-//ietf//dtd html 3.0//',
    '-//ietf//dtd html 3.2 final//',
    '-//ietf//dtd html 3.2//',
    '-//ietf//dtd html 3//',
    '-//ietf//dtd html level 0//',
    '-//ietf//dtd html level 1//',
    '-//ietf//dtd html level 2//',
    '-//ietf//dtd html level 3//',
    '-//ietf//dtd html strict level 0//',
    '-//ietf//dtd html strict level 1//',
    '-//ietf//dtd html strict level 2//',
    '-//ietf//dtd html strict level 3//',
    '-//ietf//dtd html strict//',
    '-//ietf//dtd html//',
    '-//metrius//dtd metrius presentational//',
    '-//microsoft//dtd internet explorer 2.0 html strict//',
    '-//microsoft//dtd internet explorer 2.0 html//',
    '-//microsoft//dtd internet explorer 2.0 tables//',
    '-//microsoft//dtd internet explorer 3.0 html strict//',
    '-//microsoft//dtd internet explorer 3.0 html//',
    '-//microsoft//dtd internet explorer 3.0 tables//',
    '-//netscape comm. corp.//dtd html//',
    '-//netscape comm. corp.//dtd strict html//',
    "-//o'reilly and associates//dtd html 2.0//",
    "-//o'reilly and associates//dtd html extended 1.0//",
    "-//o'reilly and associates//dtd html extended relaxed 1.0//",
    '-//sq//dtd html 2.0 hotmetal + extensions//',
    '-//softquad software//dtd hotmetal pro 6.0::19990601::extensions to html 4.0//',
    '-//softquad//dtd hotmetal pro 4.0::19971010::extensions to html 4.0//',
    '-//spyglass//dtd html 2.0 extended//',
    '-//sun microsystems corp.//dtd hotjava html//',
    '-//sun microsystems corp.//dtd hotjava strict html//',
    '-//w3c//dtd html 3 1995-03-24//',
    '-//w3c//dtd html 3.2 draft//',
    '-//w3c//dtd html 3.2 final//',
    '-//w3c//dtd html 3.2//',
    '-//w3c//dtd html 3.2s draft//',
    '-//w3c//dtd html 4.0 frameset//',
    '-//w3c//dtd html 4.0 transitional//',
    '-//w3c//dtd html experimental 19960712//',
    '-//w3c//dtd html experimental 970421//',
    '-//w3c//dtd w3 html//',
    '-//w3o//dtd w3 html 3.0//',
    '-//webtechs//dtd mozilla html 2.0//',
    '-//webtechs//dtd mozilla html//'
];
const QUIRKS_MODE_NO_SYSTEM_ID_PUBLIC_ID_PREFIXES = [
    ...QUIRKS_MODE_PUBLIC_ID_PREFIXES,
    '-//w3c//dtd html 4.01 frameset//',
    '-//w3c//dtd html 4.01 transitional//'
];
const QUIRKS_MODE_PUBLIC_IDS = new Set([
    '-//w3o//dtd w3 html strict 3.0//en//',
    '-/w3c/dtd html 4.0 transitional/en',
    'html'
]);
const LIMITED_QUIRKS_PUBLIC_ID_PREFIXES = [
    '-//w3c//dtd xhtml 1.0 frameset//',
    '-//w3c//dtd xhtml 1.0 transitional//'
];
const LIMITED_QUIRKS_WITH_SYSTEM_ID_PUBLIC_ID_PREFIXES = [
    ...LIMITED_QUIRKS_PUBLIC_ID_PREFIXES,
    '-//w3c//dtd html 4.01 frameset//',
    '-//w3c//dtd html 4.01 transitional//'
];
//Utils
function hasPrefix(publicId, prefixes) {
    return prefixes.some((prefix)=>publicId.startsWith(prefix));
}
function isConforming(token) {
    return token.name === VALID_DOCTYPE_NAME && token.publicId === null && (token.systemId === null || token.systemId === VALID_SYSTEM_ID);
}
function getDocumentMode(token) {
    if (token.name !== VALID_DOCTYPE_NAME) {
        return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DOCUMENT_MODE"].QUIRKS;
    }
    const { systemId } = token;
    if (systemId && systemId.toLowerCase() === QUIRKS_MODE_SYSTEM_ID) {
        return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DOCUMENT_MODE"].QUIRKS;
    }
    let { publicId } = token;
    if (publicId !== null) {
        publicId = publicId.toLowerCase();
        if (QUIRKS_MODE_PUBLIC_IDS.has(publicId)) {
            return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DOCUMENT_MODE"].QUIRKS;
        }
        let prefixes = systemId === null ? QUIRKS_MODE_NO_SYSTEM_ID_PUBLIC_ID_PREFIXES : QUIRKS_MODE_PUBLIC_ID_PREFIXES;
        if (hasPrefix(publicId, prefixes)) {
            return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DOCUMENT_MODE"].QUIRKS;
        }
        prefixes = systemId === null ? LIMITED_QUIRKS_PUBLIC_ID_PREFIXES : LIMITED_QUIRKS_WITH_SYSTEM_ID_PUBLIC_ID_PREFIXES;
        if (hasPrefix(publicId, prefixes)) {
            return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DOCUMENT_MODE"].LIMITED_QUIRKS;
        }
    }
    return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DOCUMENT_MODE"].NO_QUIRKS;
}
}),
"[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/foreign-content.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "SVG_TAG_NAMES_ADJUSTMENT_MAP",
    ()=>SVG_TAG_NAMES_ADJUSTMENT_MAP,
    "adjustTokenMathMLAttrs",
    ()=>adjustTokenMathMLAttrs,
    "adjustTokenSVGAttrs",
    ()=>adjustTokenSVGAttrs,
    "adjustTokenSVGTagName",
    ()=>adjustTokenSVGTagName,
    "adjustTokenXMLAttrs",
    ()=>adjustTokenXMLAttrs,
    "causesExit",
    ()=>causesExit,
    "isIntegrationPoint",
    ()=>isIntegrationPoint
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/html.js [app-client] (ecmascript)");
;
//MIME types
const MIME_TYPES = {
    TEXT_HTML: 'text/html',
    APPLICATION_XML: 'application/xhtml+xml'
};
//Attributes
const DEFINITION_URL_ATTR = 'definitionurl';
const ADJUSTED_DEFINITION_URL_ATTR = 'definitionURL';
const SVG_ATTRS_ADJUSTMENT_MAP = new Map([
    'attributeName',
    'attributeType',
    'baseFrequency',
    'baseProfile',
    'calcMode',
    'clipPathUnits',
    'diffuseConstant',
    'edgeMode',
    'filterUnits',
    'glyphRef',
    'gradientTransform',
    'gradientUnits',
    'kernelMatrix',
    'kernelUnitLength',
    'keyPoints',
    'keySplines',
    'keyTimes',
    'lengthAdjust',
    'limitingConeAngle',
    'markerHeight',
    'markerUnits',
    'markerWidth',
    'maskContentUnits',
    'maskUnits',
    'numOctaves',
    'pathLength',
    'patternContentUnits',
    'patternTransform',
    'patternUnits',
    'pointsAtX',
    'pointsAtY',
    'pointsAtZ',
    'preserveAlpha',
    'preserveAspectRatio',
    'primitiveUnits',
    'refX',
    'refY',
    'repeatCount',
    'repeatDur',
    'requiredExtensions',
    'requiredFeatures',
    'specularConstant',
    'specularExponent',
    'spreadMethod',
    'startOffset',
    'stdDeviation',
    'stitchTiles',
    'surfaceScale',
    'systemLanguage',
    'tableValues',
    'targetX',
    'targetY',
    'textLength',
    'viewBox',
    'viewTarget',
    'xChannelSelector',
    'yChannelSelector',
    'zoomAndPan'
].map((attr)=>[
        attr.toLowerCase(),
        attr
    ]));
const XML_ATTRS_ADJUSTMENT_MAP = new Map([
    [
        'xlink:actuate',
        {
            prefix: 'xlink',
            name: 'actuate',
            namespace: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].XLINK
        }
    ],
    [
        'xlink:arcrole',
        {
            prefix: 'xlink',
            name: 'arcrole',
            namespace: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].XLINK
        }
    ],
    [
        'xlink:href',
        {
            prefix: 'xlink',
            name: 'href',
            namespace: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].XLINK
        }
    ],
    [
        'xlink:role',
        {
            prefix: 'xlink',
            name: 'role',
            namespace: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].XLINK
        }
    ],
    [
        'xlink:show',
        {
            prefix: 'xlink',
            name: 'show',
            namespace: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].XLINK
        }
    ],
    [
        'xlink:title',
        {
            prefix: 'xlink',
            name: 'title',
            namespace: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].XLINK
        }
    ],
    [
        'xlink:type',
        {
            prefix: 'xlink',
            name: 'type',
            namespace: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].XLINK
        }
    ],
    [
        'xml:lang',
        {
            prefix: 'xml',
            name: 'lang',
            namespace: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].XML
        }
    ],
    [
        'xml:space',
        {
            prefix: 'xml',
            name: 'space',
            namespace: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].XML
        }
    ],
    [
        'xmlns',
        {
            prefix: '',
            name: 'xmlns',
            namespace: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].XMLNS
        }
    ],
    [
        'xmlns:xlink',
        {
            prefix: 'xmlns',
            name: 'xlink',
            namespace: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].XMLNS
        }
    ]
]);
const SVG_TAG_NAMES_ADJUSTMENT_MAP = new Map([
    'altGlyph',
    'altGlyphDef',
    'altGlyphItem',
    'animateColor',
    'animateMotion',
    'animateTransform',
    'clipPath',
    'feBlend',
    'feColorMatrix',
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
    'foreignObject',
    'glyphRef',
    'linearGradient',
    'radialGradient',
    'textPath'
].map((tn)=>[
        tn.toLowerCase(),
        tn
    ]));
//Tags that causes exit from foreign content
const EXITS_FOREIGN_CONTENT = new Set([
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].B,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BIG,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BLOCKQUOTE,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BODY,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BR,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CENTER,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CODE,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DD,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DIV,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DL,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DT,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].EM,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].EMBED,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].H1,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].H2,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].H3,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].H4,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].H5,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].H6,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HEAD,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HR,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].I,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].IMG,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].LI,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].LISTING,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].MENU,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].META,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NOBR,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OL,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].P,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].PRE,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].RUBY,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].S,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SMALL,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SPAN,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].STRONG,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].STRIKE,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SUB,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SUP,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TT,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].U,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].UL,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].VAR
]);
function causesExit(startTagToken) {
    const tn = startTagToken.tagID;
    const isFontWithAttrs = tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FONT && startTagToken.attrs.some(({ name })=>name === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ATTRS"].COLOR || name === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ATTRS"].SIZE || name === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ATTRS"].FACE);
    return isFontWithAttrs || EXITS_FOREIGN_CONTENT.has(tn);
}
function adjustTokenMathMLAttrs(token) {
    for(let i = 0; i < token.attrs.length; i++){
        if (token.attrs[i].name === DEFINITION_URL_ATTR) {
            token.attrs[i].name = ADJUSTED_DEFINITION_URL_ATTR;
            break;
        }
    }
}
function adjustTokenSVGAttrs(token) {
    for(let i = 0; i < token.attrs.length; i++){
        const adjustedAttrName = SVG_ATTRS_ADJUSTMENT_MAP.get(token.attrs[i].name);
        if (adjustedAttrName != null) {
            token.attrs[i].name = adjustedAttrName;
        }
    }
}
function adjustTokenXMLAttrs(token) {
    for(let i = 0; i < token.attrs.length; i++){
        const adjustedAttrEntry = XML_ATTRS_ADJUSTMENT_MAP.get(token.attrs[i].name);
        if (adjustedAttrEntry) {
            token.attrs[i].prefix = adjustedAttrEntry.prefix;
            token.attrs[i].name = adjustedAttrEntry.name;
            token.attrs[i].namespace = adjustedAttrEntry.namespace;
        }
    }
}
function adjustTokenSVGTagName(token) {
    const adjustedTagName = SVG_TAG_NAMES_ADJUSTMENT_MAP.get(token.tagName);
    if (adjustedTagName != null) {
        token.tagName = adjustedTagName;
        token.tagID = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTagID"])(token.tagName);
    }
}
//Integration points
function isMathMLTextIntegrationPoint(tn, ns) {
    return ns === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].MATHML && (tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].MI || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].MO || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].MN || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].MS || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].MTEXT);
}
function isHtmlIntegrationPoint(tn, ns, attrs) {
    if (ns === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].MATHML && tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].ANNOTATION_XML) {
        for(let i = 0; i < attrs.length; i++){
            if (attrs[i].name === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ATTRS"].ENCODING) {
                const value = attrs[i].value.toLowerCase();
                return value === MIME_TYPES.TEXT_HTML || value === MIME_TYPES.APPLICATION_XML;
            }
        }
    }
    return ns === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].SVG && (tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FOREIGN_OBJECT || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DESC || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TITLE);
}
function isIntegrationPoint(tn, ns, attrs, foreignNS) {
    return (!foreignNS || foreignNS === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML) && isHtmlIntegrationPoint(tn, ns, attrs) || (!foreignNS || foreignNS === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].MATHML) && isMathMLTextIntegrationPoint(tn, ns);
}
}),
"[project]/coding/projects/LangBot/web/node_modules/parse5/dist/parser/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Parser",
    ()=>Parser
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tokenizer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/tokenizer/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$parser$2f$open$2d$element$2d$stack$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/parser/open-element-stack.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$parser$2f$formatting$2d$element$2d$list$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/parser/formatting-element-list.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tree$2d$adapters$2f$default$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/tree-adapters/default.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$doctype$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/doctype.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$foreign$2d$content$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/foreign-content.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/error-codes.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/unicode.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/html.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/token.js [app-client] (ecmascript)");
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
//Misc constants
const HIDDEN_INPUT_TYPE = 'hidden';
//Adoption agency loops iteration count
const AA_OUTER_LOOP_ITER = 8;
const AA_INNER_LOOP_ITER = 3;
//Insertion modes
var InsertionMode;
(function(InsertionMode) {
    InsertionMode[InsertionMode["INITIAL"] = 0] = "INITIAL";
    InsertionMode[InsertionMode["BEFORE_HTML"] = 1] = "BEFORE_HTML";
    InsertionMode[InsertionMode["BEFORE_HEAD"] = 2] = "BEFORE_HEAD";
    InsertionMode[InsertionMode["IN_HEAD"] = 3] = "IN_HEAD";
    InsertionMode[InsertionMode["IN_HEAD_NO_SCRIPT"] = 4] = "IN_HEAD_NO_SCRIPT";
    InsertionMode[InsertionMode["AFTER_HEAD"] = 5] = "AFTER_HEAD";
    InsertionMode[InsertionMode["IN_BODY"] = 6] = "IN_BODY";
    InsertionMode[InsertionMode["TEXT"] = 7] = "TEXT";
    InsertionMode[InsertionMode["IN_TABLE"] = 8] = "IN_TABLE";
    InsertionMode[InsertionMode["IN_TABLE_TEXT"] = 9] = "IN_TABLE_TEXT";
    InsertionMode[InsertionMode["IN_CAPTION"] = 10] = "IN_CAPTION";
    InsertionMode[InsertionMode["IN_COLUMN_GROUP"] = 11] = "IN_COLUMN_GROUP";
    InsertionMode[InsertionMode["IN_TABLE_BODY"] = 12] = "IN_TABLE_BODY";
    InsertionMode[InsertionMode["IN_ROW"] = 13] = "IN_ROW";
    InsertionMode[InsertionMode["IN_CELL"] = 14] = "IN_CELL";
    InsertionMode[InsertionMode["IN_SELECT"] = 15] = "IN_SELECT";
    InsertionMode[InsertionMode["IN_SELECT_IN_TABLE"] = 16] = "IN_SELECT_IN_TABLE";
    InsertionMode[InsertionMode["IN_TEMPLATE"] = 17] = "IN_TEMPLATE";
    InsertionMode[InsertionMode["AFTER_BODY"] = 18] = "AFTER_BODY";
    InsertionMode[InsertionMode["IN_FRAMESET"] = 19] = "IN_FRAMESET";
    InsertionMode[InsertionMode["AFTER_FRAMESET"] = 20] = "AFTER_FRAMESET";
    InsertionMode[InsertionMode["AFTER_AFTER_BODY"] = 21] = "AFTER_AFTER_BODY";
    InsertionMode[InsertionMode["AFTER_AFTER_FRAMESET"] = 22] = "AFTER_AFTER_FRAMESET";
})(InsertionMode || (InsertionMode = {}));
const BASE_LOC = {
    startLine: -1,
    startCol: -1,
    startOffset: -1,
    endLine: -1,
    endCol: -1,
    endOffset: -1
};
const TABLE_STRUCTURE_TAGS = new Set([
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TBODY,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TFOOT,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].THEAD,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR
]);
const defaultParserOptions = {
    scriptingEnabled: true,
    sourceCodeLocationInfo: false,
    treeAdapter: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tree$2d$adapters$2f$default$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["defaultTreeAdapter"],
    onParseError: null
};
class Parser {
    constructor(options, document, /** @internal */ fragmentContext = null, /** @internal */ scriptHandler = null){
        this.fragmentContext = fragmentContext;
        this.scriptHandler = scriptHandler;
        this.currentToken = null;
        this.stopped = false;
        /** @internal */ this.insertionMode = InsertionMode.INITIAL;
        /** @internal */ this.originalInsertionMode = InsertionMode.INITIAL;
        /** @internal */ this.headElement = null;
        /** @internal */ this.formElement = null;
        /** Indicates that the current node is not an element in the HTML namespace */ this.currentNotInHTML = false;
        /**
         * The template insertion mode stack is maintained from the left.
         * Ie. the topmost element will always have index 0.
         *
         * @internal
         */ this.tmplInsertionModeStack = [];
        /** @internal */ this.pendingCharacterTokens = [];
        /** @internal */ this.hasNonWhitespacePendingCharacterToken = false;
        /** @internal */ this.framesetOk = true;
        /** @internal */ this.skipNextNewLine = false;
        /** @internal */ this.fosterParentingEnabled = false;
        this.options = {
            ...defaultParserOptions,
            ...options
        };
        this.treeAdapter = this.options.treeAdapter;
        this.onParseError = this.options.onParseError;
        // Always enable location info if we report parse errors.
        if (this.onParseError) {
            this.options.sourceCodeLocationInfo = true;
        }
        this.document = document !== null && document !== void 0 ? document : this.treeAdapter.createDocument();
        this.tokenizer = new __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tokenizer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Tokenizer"](this.options, this);
        this.activeFormattingElements = new __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$parser$2f$formatting$2d$element$2d$list$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormattingElementList"](this.treeAdapter);
        this.fragmentContextID = fragmentContext ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTagID"])(this.treeAdapter.getTagName(fragmentContext)) : __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].UNKNOWN;
        this._setContextModes(fragmentContext !== null && fragmentContext !== void 0 ? fragmentContext : this.document, this.fragmentContextID);
        this.openElements = new __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$parser$2f$open$2d$element$2d$stack$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["OpenElementStack"](this.document, this.treeAdapter, this);
    }
    // API
    static parse(html, options) {
        const parser = new this(options);
        parser.tokenizer.write(html, true);
        return parser.document;
    }
    static getFragmentParser(fragmentContext, options) {
        const opts = {
            ...defaultParserOptions,
            ...options
        };
        //NOTE: use a <template> element as the fragment context if no context element was provided,
        //so we will parse in a "forgiving" manner
        fragmentContext !== null && fragmentContext !== void 0 ? fragmentContext : fragmentContext = opts.treeAdapter.createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].TEMPLATE, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML, []);
        //NOTE: create a fake element which will be used as the `document` for fragment parsing.
        //This is important for jsdom, where a new `document` cannot be created. This led to
        //fragment parsing messing with the main `document`.
        const documentMock = opts.treeAdapter.createElement('documentmock', __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML, []);
        const parser = new this(opts, documentMock, fragmentContext);
        if (parser.fragmentContextID === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE) {
            parser.tmplInsertionModeStack.unshift(InsertionMode.IN_TEMPLATE);
        }
        parser._initTokenizerForFragmentParsing();
        parser._insertFakeRootElement();
        parser._resetInsertionMode();
        parser._findFormInFragmentContext();
        return parser;
    }
    getFragment() {
        const rootElement = this.treeAdapter.getFirstChild(this.document);
        const fragment = this.treeAdapter.createDocumentFragment();
        this._adoptNodes(rootElement, fragment);
        return fragment;
    }
    //Errors
    /** @internal */ _err(token, code, beforeToken) {
        var _a;
        if (!this.onParseError) return;
        const loc = (_a = token.location) !== null && _a !== void 0 ? _a : BASE_LOC;
        const err = {
            code,
            startLine: loc.startLine,
            startCol: loc.startCol,
            startOffset: loc.startOffset,
            endLine: beforeToken ? loc.startLine : loc.endLine,
            endCol: beforeToken ? loc.startCol : loc.endCol,
            endOffset: beforeToken ? loc.startOffset : loc.endOffset
        };
        this.onParseError(err);
    }
    //Stack events
    /** @internal */ onItemPush(node, tid, isTop) {
        var _a, _b;
        (_b = (_a = this.treeAdapter).onItemPush) === null || _b === void 0 ? void 0 : _b.call(_a, node);
        if (isTop && this.openElements.stackTop > 0) this._setContextModes(node, tid);
    }
    /** @internal */ onItemPop(node, isTop) {
        var _a, _b;
        if (this.options.sourceCodeLocationInfo) {
            this._setEndLocation(node, this.currentToken);
        }
        (_b = (_a = this.treeAdapter).onItemPop) === null || _b === void 0 ? void 0 : _b.call(_a, node, this.openElements.current);
        if (isTop) {
            let current;
            let currentTagId;
            if (this.openElements.stackTop === 0 && this.fragmentContext) {
                current = this.fragmentContext;
                currentTagId = this.fragmentContextID;
            } else {
                ({ current, currentTagId } = this.openElements);
            }
            this._setContextModes(current, currentTagId);
        }
    }
    _setContextModes(current, tid) {
        const isHTML = current === this.document || current && this.treeAdapter.getNamespaceURI(current) === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML;
        this.currentNotInHTML = !isHTML;
        this.tokenizer.inForeignNode = !isHTML && current !== undefined && tid !== undefined && !this._isIntegrationPoint(tid, current);
    }
    /** @protected */ _switchToTextParsing(currentToken, nextTokenizerState) {
        this._insertElement(currentToken, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
        this.tokenizer.state = nextTokenizerState;
        this.originalInsertionMode = this.insertionMode;
        this.insertionMode = InsertionMode.TEXT;
    }
    switchToPlaintextParsing() {
        this.insertionMode = InsertionMode.TEXT;
        this.originalInsertionMode = InsertionMode.IN_BODY;
        this.tokenizer.state = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tokenizer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenizerMode"].PLAINTEXT;
    }
    //Fragment parsing
    /** @protected */ _getAdjustedCurrentElement() {
        return this.openElements.stackTop === 0 && this.fragmentContext ? this.fragmentContext : this.openElements.current;
    }
    /** @protected */ _findFormInFragmentContext() {
        let node = this.fragmentContext;
        while(node){
            if (this.treeAdapter.getTagName(node) === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].FORM) {
                this.formElement = node;
                break;
            }
            node = this.treeAdapter.getParentNode(node);
        }
    }
    _initTokenizerForFragmentParsing() {
        if (!this.fragmentContext || this.treeAdapter.getNamespaceURI(this.fragmentContext) !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML) {
            return;
        }
        switch(this.fragmentContextID){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TITLE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEXTAREA:
                {
                    this.tokenizer.state = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tokenizer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenizerMode"].RCDATA;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].STYLE:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].XMP:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].IFRAME:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NOEMBED:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NOFRAMES:
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NOSCRIPT:
                {
                    this.tokenizer.state = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tokenizer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenizerMode"].RAWTEXT;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SCRIPT:
                {
                    this.tokenizer.state = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tokenizer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenizerMode"].SCRIPT_DATA;
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].PLAINTEXT:
                {
                    this.tokenizer.state = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tokenizer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenizerMode"].PLAINTEXT;
                    break;
                }
            default:
        }
    }
    //Tree mutation
    /** @protected */ _setDocumentType(token) {
        const name = token.name || '';
        const publicId = token.publicId || '';
        const systemId = token.systemId || '';
        this.treeAdapter.setDocumentType(this.document, name, publicId, systemId);
        if (token.location) {
            const documentChildren = this.treeAdapter.getChildNodes(this.document);
            const docTypeNode = documentChildren.find((node)=>this.treeAdapter.isDocumentTypeNode(node));
            if (docTypeNode) {
                this.treeAdapter.setNodeSourceCodeLocation(docTypeNode, token.location);
            }
        }
    }
    /** @protected */ _attachElementToTree(element, location) {
        if (this.options.sourceCodeLocationInfo) {
            const loc = location && {
                ...location,
                startTag: location
            };
            this.treeAdapter.setNodeSourceCodeLocation(element, loc);
        }
        if (this._shouldFosterParentOnInsertion()) {
            this._fosterParentElement(element);
        } else {
            const parent = this.openElements.currentTmplContentOrNode;
            this.treeAdapter.appendChild(parent !== null && parent !== void 0 ? parent : this.document, element);
        }
    }
    /**
     * For self-closing tags. Add an element to the tree, but skip adding it
     * to the stack.
     */ /** @protected */ _appendElement(token, namespaceURI) {
        const element = this.treeAdapter.createElement(token.tagName, namespaceURI, token.attrs);
        this._attachElementToTree(element, token.location);
    }
    /** @protected */ _insertElement(token, namespaceURI) {
        const element = this.treeAdapter.createElement(token.tagName, namespaceURI, token.attrs);
        this._attachElementToTree(element, token.location);
        this.openElements.push(element, token.tagID);
    }
    /** @protected */ _insertFakeElement(tagName, tagID) {
        const element = this.treeAdapter.createElement(tagName, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML, []);
        this._attachElementToTree(element, null);
        this.openElements.push(element, tagID);
    }
    /** @protected */ _insertTemplate(token) {
        const tmpl = this.treeAdapter.createElement(token.tagName, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML, token.attrs);
        const content = this.treeAdapter.createDocumentFragment();
        this.treeAdapter.setTemplateContent(tmpl, content);
        this._attachElementToTree(tmpl, token.location);
        this.openElements.push(tmpl, token.tagID);
        if (this.options.sourceCodeLocationInfo) this.treeAdapter.setNodeSourceCodeLocation(content, null);
    }
    /** @protected */ _insertFakeRootElement() {
        const element = this.treeAdapter.createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].HTML, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML, []);
        if (this.options.sourceCodeLocationInfo) this.treeAdapter.setNodeSourceCodeLocation(element, null);
        this.treeAdapter.appendChild(this.openElements.current, element);
        this.openElements.push(element, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML);
    }
    /** @protected */ _appendCommentNode(token, parent) {
        const commentNode = this.treeAdapter.createCommentNode(token.data);
        this.treeAdapter.appendChild(parent, commentNode);
        if (this.options.sourceCodeLocationInfo) {
            this.treeAdapter.setNodeSourceCodeLocation(commentNode, token.location);
        }
    }
    /** @protected */ _insertCharacters(token) {
        let parent;
        let beforeElement;
        if (this._shouldFosterParentOnInsertion()) {
            ({ parent, beforeElement } = this._findFosterParentingLocation());
            if (beforeElement) {
                this.treeAdapter.insertTextBefore(parent, token.chars, beforeElement);
            } else {
                this.treeAdapter.insertText(parent, token.chars);
            }
        } else {
            parent = this.openElements.currentTmplContentOrNode;
            this.treeAdapter.insertText(parent, token.chars);
        }
        if (!token.location) return;
        const siblings = this.treeAdapter.getChildNodes(parent);
        const textNodeIdx = beforeElement ? siblings.lastIndexOf(beforeElement) : siblings.length;
        const textNode = siblings[textNodeIdx - 1];
        //NOTE: if we have a location assigned by another token, then just update the end position
        const tnLoc = this.treeAdapter.getNodeSourceCodeLocation(textNode);
        if (tnLoc) {
            const { endLine, endCol, endOffset } = token.location;
            this.treeAdapter.updateNodeSourceCodeLocation(textNode, {
                endLine,
                endCol,
                endOffset
            });
        } else if (this.options.sourceCodeLocationInfo) {
            this.treeAdapter.setNodeSourceCodeLocation(textNode, token.location);
        }
    }
    /** @protected */ _adoptNodes(donor, recipient) {
        for(let child = this.treeAdapter.getFirstChild(donor); child; child = this.treeAdapter.getFirstChild(donor)){
            this.treeAdapter.detachNode(child);
            this.treeAdapter.appendChild(recipient, child);
        }
    }
    /** @protected */ _setEndLocation(element, closingToken) {
        if (this.treeAdapter.getNodeSourceCodeLocation(element) && closingToken.location) {
            const ctLoc = closingToken.location;
            const tn = this.treeAdapter.getTagName(element);
            const endLoc = // NOTE: For cases like <p> <p> </p> - First 'p' closes without a closing
            // tag and for cases like <td> <p> </td> - 'p' closes without a closing tag.
            closingToken.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].END_TAG && tn === closingToken.tagName ? {
                endTag: {
                    ...ctLoc
                },
                endLine: ctLoc.endLine,
                endCol: ctLoc.endCol,
                endOffset: ctLoc.endOffset
            } : {
                endLine: ctLoc.startLine,
                endCol: ctLoc.startCol,
                endOffset: ctLoc.startOffset
            };
            this.treeAdapter.updateNodeSourceCodeLocation(element, endLoc);
        }
    }
    //Token processing
    shouldProcessStartTagTokenInForeignContent(token) {
        // Check that neither current === document, or ns === NS.HTML
        if (!this.currentNotInHTML) return false;
        let current;
        let currentTagId;
        if (this.openElements.stackTop === 0 && this.fragmentContext) {
            current = this.fragmentContext;
            currentTagId = this.fragmentContextID;
        } else {
            ({ current, currentTagId } = this.openElements);
        }
        if (token.tagID === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SVG && this.treeAdapter.getTagName(current) === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].ANNOTATION_XML && this.treeAdapter.getNamespaceURI(current) === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].MATHML) {
            return false;
        }
        return(// Check that `current` is not an integration point for HTML or MathML elements.
        this.tokenizer.inForeignNode || (token.tagID === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].MGLYPH || token.tagID === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].MALIGNMARK) && currentTagId !== undefined && !this._isIntegrationPoint(currentTagId, current, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML));
    }
    /** @protected */ _processToken(token) {
        switch(token.type){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].CHARACTER:
                {
                    this.onCharacter(token);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].NULL_CHARACTER:
                {
                    this.onNullCharacter(token);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].COMMENT:
                {
                    this.onComment(token);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].DOCTYPE:
                {
                    this.onDoctype(token);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].START_TAG:
                {
                    this._processStartTag(token);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].END_TAG:
                {
                    this.onEndTag(token);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].EOF:
                {
                    this.onEof(token);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].WHITESPACE_CHARACTER:
                {
                    this.onWhitespaceCharacter(token);
                    break;
                }
        }
    }
    //Integration points
    /** @protected */ _isIntegrationPoint(tid, element, foreignNS) {
        const ns = this.treeAdapter.getNamespaceURI(element);
        const attrs = this.treeAdapter.getAttrList(element);
        return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$foreign$2d$content$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isIntegrationPoint"](tid, ns, attrs, foreignNS);
    }
    //Active formatting elements reconstruction
    /** @protected */ _reconstructActiveFormattingElements() {
        const listLength = this.activeFormattingElements.entries.length;
        if (listLength) {
            const endIndex = this.activeFormattingElements.entries.findIndex((entry)=>entry.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$parser$2f$formatting$2d$element$2d$list$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["EntryType"].Marker || this.openElements.contains(entry.element));
            const unopenIdx = endIndex === -1 ? listLength - 1 : endIndex - 1;
            for(let i = unopenIdx; i >= 0; i--){
                const entry = this.activeFormattingElements.entries[i];
                this._insertElement(entry.token, this.treeAdapter.getNamespaceURI(entry.element));
                entry.element = this.openElements.current;
            }
        }
    }
    //Close elements
    /** @protected */ _closeTableCell() {
        this.openElements.generateImpliedEndTags();
        this.openElements.popUntilTableCellPopped();
        this.activeFormattingElements.clearToLastMarker();
        this.insertionMode = InsertionMode.IN_ROW;
    }
    /** @protected */ _closePElement() {
        this.openElements.generateImpliedEndTagsWithExclusion(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].P);
        this.openElements.popUntilTagNamePopped(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].P);
    }
    //Insertion modes
    /** @protected */ _resetInsertionMode() {
        for(let i = this.openElements.stackTop; i >= 0; i--){
            //Insertion mode reset map
            switch(i === 0 && this.fragmentContext ? this.fragmentContextID : this.openElements.tagIDs[i]){
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR:
                    {
                        this.insertionMode = InsertionMode.IN_ROW;
                        return;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TBODY:
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].THEAD:
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TFOOT:
                    {
                        this.insertionMode = InsertionMode.IN_TABLE_BODY;
                        return;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CAPTION:
                    {
                        this.insertionMode = InsertionMode.IN_CAPTION;
                        return;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COLGROUP:
                    {
                        this.insertionMode = InsertionMode.IN_COLUMN_GROUP;
                        return;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE:
                    {
                        this.insertionMode = InsertionMode.IN_TABLE;
                        return;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BODY:
                    {
                        this.insertionMode = InsertionMode.IN_BODY;
                        return;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FRAMESET:
                    {
                        this.insertionMode = InsertionMode.IN_FRAMESET;
                        return;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SELECT:
                    {
                        this._resetInsertionModeForSelect(i);
                        return;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE:
                    {
                        this.insertionMode = this.tmplInsertionModeStack[0];
                        return;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML:
                    {
                        this.insertionMode = this.headElement ? InsertionMode.AFTER_HEAD : InsertionMode.BEFORE_HEAD;
                        return;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TD:
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TH:
                    {
                        if (i > 0) {
                            this.insertionMode = InsertionMode.IN_CELL;
                            return;
                        }
                        break;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HEAD:
                    {
                        if (i > 0) {
                            this.insertionMode = InsertionMode.IN_HEAD;
                            return;
                        }
                        break;
                    }
            }
        }
        this.insertionMode = InsertionMode.IN_BODY;
    }
    /** @protected */ _resetInsertionModeForSelect(selectIdx) {
        if (selectIdx > 0) {
            for(let i = selectIdx - 1; i > 0; i--){
                const tn = this.openElements.tagIDs[i];
                if (tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE) {
                    break;
                } else if (tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE) {
                    this.insertionMode = InsertionMode.IN_SELECT_IN_TABLE;
                    return;
                }
            }
        }
        this.insertionMode = InsertionMode.IN_SELECT;
    }
    //Foster parenting
    /** @protected */ _isElementCausesFosterParenting(tn) {
        return TABLE_STRUCTURE_TAGS.has(tn);
    }
    /** @protected */ _shouldFosterParentOnInsertion() {
        return this.fosterParentingEnabled && this.openElements.currentTagId !== undefined && this._isElementCausesFosterParenting(this.openElements.currentTagId);
    }
    /** @protected */ _findFosterParentingLocation() {
        for(let i = this.openElements.stackTop; i >= 0; i--){
            const openElement = this.openElements.items[i];
            switch(this.openElements.tagIDs[i]){
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE:
                    {
                        if (this.treeAdapter.getNamespaceURI(openElement) === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML) {
                            return {
                                parent: this.treeAdapter.getTemplateContent(openElement),
                                beforeElement: null
                            };
                        }
                        break;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE:
                    {
                        const parent = this.treeAdapter.getParentNode(openElement);
                        if (parent) {
                            return {
                                parent,
                                beforeElement: openElement
                            };
                        }
                        return {
                            parent: this.openElements.items[i - 1],
                            beforeElement: null
                        };
                    }
                default:
            }
        }
        return {
            parent: this.openElements.items[0],
            beforeElement: null
        };
    }
    /** @protected */ _fosterParentElement(element) {
        const location = this._findFosterParentingLocation();
        if (location.beforeElement) {
            this.treeAdapter.insertBefore(location.parent, element, location.beforeElement);
        } else {
            this.treeAdapter.appendChild(location.parent, element);
        }
    }
    //Special elements
    /** @protected */ _isSpecialElement(element, id) {
        const ns = this.treeAdapter.getNamespaceURI(element);
        return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SPECIAL_ELEMENTS"][ns].has(id);
    }
    /** @internal */ onCharacter(token) {
        this.skipNextNewLine = false;
        if (this.tokenizer.inForeignNode) {
            characterInForeignContent(this, token);
            return;
        }
        switch(this.insertionMode){
            case InsertionMode.INITIAL:
                {
                    tokenInInitialMode(this, token);
                    break;
                }
            case InsertionMode.BEFORE_HTML:
                {
                    tokenBeforeHtml(this, token);
                    break;
                }
            case InsertionMode.BEFORE_HEAD:
                {
                    tokenBeforeHead(this, token);
                    break;
                }
            case InsertionMode.IN_HEAD:
                {
                    tokenInHead(this, token);
                    break;
                }
            case InsertionMode.IN_HEAD_NO_SCRIPT:
                {
                    tokenInHeadNoScript(this, token);
                    break;
                }
            case InsertionMode.AFTER_HEAD:
                {
                    tokenAfterHead(this, token);
                    break;
                }
            case InsertionMode.IN_BODY:
            case InsertionMode.IN_CAPTION:
            case InsertionMode.IN_CELL:
            case InsertionMode.IN_TEMPLATE:
                {
                    characterInBody(this, token);
                    break;
                }
            case InsertionMode.TEXT:
            case InsertionMode.IN_SELECT:
            case InsertionMode.IN_SELECT_IN_TABLE:
                {
                    this._insertCharacters(token);
                    break;
                }
            case InsertionMode.IN_TABLE:
            case InsertionMode.IN_TABLE_BODY:
            case InsertionMode.IN_ROW:
                {
                    characterInTable(this, token);
                    break;
                }
            case InsertionMode.IN_TABLE_TEXT:
                {
                    characterInTableText(this, token);
                    break;
                }
            case InsertionMode.IN_COLUMN_GROUP:
                {
                    tokenInColumnGroup(this, token);
                    break;
                }
            case InsertionMode.AFTER_BODY:
                {
                    tokenAfterBody(this, token);
                    break;
                }
            case InsertionMode.AFTER_AFTER_BODY:
                {
                    tokenAfterAfterBody(this, token);
                    break;
                }
            default:
        }
    }
    /** @internal */ onNullCharacter(token) {
        this.skipNextNewLine = false;
        if (this.tokenizer.inForeignNode) {
            nullCharacterInForeignContent(this, token);
            return;
        }
        switch(this.insertionMode){
            case InsertionMode.INITIAL:
                {
                    tokenInInitialMode(this, token);
                    break;
                }
            case InsertionMode.BEFORE_HTML:
                {
                    tokenBeforeHtml(this, token);
                    break;
                }
            case InsertionMode.BEFORE_HEAD:
                {
                    tokenBeforeHead(this, token);
                    break;
                }
            case InsertionMode.IN_HEAD:
                {
                    tokenInHead(this, token);
                    break;
                }
            case InsertionMode.IN_HEAD_NO_SCRIPT:
                {
                    tokenInHeadNoScript(this, token);
                    break;
                }
            case InsertionMode.AFTER_HEAD:
                {
                    tokenAfterHead(this, token);
                    break;
                }
            case InsertionMode.TEXT:
                {
                    this._insertCharacters(token);
                    break;
                }
            case InsertionMode.IN_TABLE:
            case InsertionMode.IN_TABLE_BODY:
            case InsertionMode.IN_ROW:
                {
                    characterInTable(this, token);
                    break;
                }
            case InsertionMode.IN_COLUMN_GROUP:
                {
                    tokenInColumnGroup(this, token);
                    break;
                }
            case InsertionMode.AFTER_BODY:
                {
                    tokenAfterBody(this, token);
                    break;
                }
            case InsertionMode.AFTER_AFTER_BODY:
                {
                    tokenAfterAfterBody(this, token);
                    break;
                }
            default:
        }
    }
    /** @internal */ onComment(token) {
        this.skipNextNewLine = false;
        if (this.currentNotInHTML) {
            appendComment(this, token);
            return;
        }
        switch(this.insertionMode){
            case InsertionMode.INITIAL:
            case InsertionMode.BEFORE_HTML:
            case InsertionMode.BEFORE_HEAD:
            case InsertionMode.IN_HEAD:
            case InsertionMode.IN_HEAD_NO_SCRIPT:
            case InsertionMode.AFTER_HEAD:
            case InsertionMode.IN_BODY:
            case InsertionMode.IN_TABLE:
            case InsertionMode.IN_CAPTION:
            case InsertionMode.IN_COLUMN_GROUP:
            case InsertionMode.IN_TABLE_BODY:
            case InsertionMode.IN_ROW:
            case InsertionMode.IN_CELL:
            case InsertionMode.IN_SELECT:
            case InsertionMode.IN_SELECT_IN_TABLE:
            case InsertionMode.IN_TEMPLATE:
            case InsertionMode.IN_FRAMESET:
            case InsertionMode.AFTER_FRAMESET:
                {
                    appendComment(this, token);
                    break;
                }
            case InsertionMode.IN_TABLE_TEXT:
                {
                    tokenInTableText(this, token);
                    break;
                }
            case InsertionMode.AFTER_BODY:
                {
                    appendCommentToRootHtmlElement(this, token);
                    break;
                }
            case InsertionMode.AFTER_AFTER_BODY:
            case InsertionMode.AFTER_AFTER_FRAMESET:
                {
                    appendCommentToDocument(this, token);
                    break;
                }
            default:
        }
    }
    /** @internal */ onDoctype(token) {
        this.skipNextNewLine = false;
        switch(this.insertionMode){
            case InsertionMode.INITIAL:
                {
                    doctypeInInitialMode(this, token);
                    break;
                }
            case InsertionMode.BEFORE_HEAD:
            case InsertionMode.IN_HEAD:
            case InsertionMode.IN_HEAD_NO_SCRIPT:
            case InsertionMode.AFTER_HEAD:
                {
                    this._err(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].misplacedDoctype);
                    break;
                }
            case InsertionMode.IN_TABLE_TEXT:
                {
                    tokenInTableText(this, token);
                    break;
                }
            default:
        }
    }
    /** @internal */ onStartTag(token) {
        this.skipNextNewLine = false;
        this.currentToken = token;
        this._processStartTag(token);
        if (token.selfClosing && !token.ackSelfClosing) {
            this._err(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].nonVoidHtmlElementStartTagWithTrailingSolidus);
        }
    }
    /**
     * Processes a given start tag.
     *
     * `onStartTag` checks if a self-closing tag was recognized. When a token
     * is moved inbetween multiple insertion modes, this check for self-closing
     * could lead to false positives. To avoid this, `_processStartTag` is used
     * for nested calls.
     *
     * @param token The token to process.
     * @protected
     */ _processStartTag(token) {
        if (this.shouldProcessStartTagTokenInForeignContent(token)) {
            startTagInForeignContent(this, token);
        } else {
            this._startTagOutsideForeignContent(token);
        }
    }
    /** @protected */ _startTagOutsideForeignContent(token) {
        switch(this.insertionMode){
            case InsertionMode.INITIAL:
                {
                    tokenInInitialMode(this, token);
                    break;
                }
            case InsertionMode.BEFORE_HTML:
                {
                    startTagBeforeHtml(this, token);
                    break;
                }
            case InsertionMode.BEFORE_HEAD:
                {
                    startTagBeforeHead(this, token);
                    break;
                }
            case InsertionMode.IN_HEAD:
                {
                    startTagInHead(this, token);
                    break;
                }
            case InsertionMode.IN_HEAD_NO_SCRIPT:
                {
                    startTagInHeadNoScript(this, token);
                    break;
                }
            case InsertionMode.AFTER_HEAD:
                {
                    startTagAfterHead(this, token);
                    break;
                }
            case InsertionMode.IN_BODY:
                {
                    startTagInBody(this, token);
                    break;
                }
            case InsertionMode.IN_TABLE:
                {
                    startTagInTable(this, token);
                    break;
                }
            case InsertionMode.IN_TABLE_TEXT:
                {
                    tokenInTableText(this, token);
                    break;
                }
            case InsertionMode.IN_CAPTION:
                {
                    startTagInCaption(this, token);
                    break;
                }
            case InsertionMode.IN_COLUMN_GROUP:
                {
                    startTagInColumnGroup(this, token);
                    break;
                }
            case InsertionMode.IN_TABLE_BODY:
                {
                    startTagInTableBody(this, token);
                    break;
                }
            case InsertionMode.IN_ROW:
                {
                    startTagInRow(this, token);
                    break;
                }
            case InsertionMode.IN_CELL:
                {
                    startTagInCell(this, token);
                    break;
                }
            case InsertionMode.IN_SELECT:
                {
                    startTagInSelect(this, token);
                    break;
                }
            case InsertionMode.IN_SELECT_IN_TABLE:
                {
                    startTagInSelectInTable(this, token);
                    break;
                }
            case InsertionMode.IN_TEMPLATE:
                {
                    startTagInTemplate(this, token);
                    break;
                }
            case InsertionMode.AFTER_BODY:
                {
                    startTagAfterBody(this, token);
                    break;
                }
            case InsertionMode.IN_FRAMESET:
                {
                    startTagInFrameset(this, token);
                    break;
                }
            case InsertionMode.AFTER_FRAMESET:
                {
                    startTagAfterFrameset(this, token);
                    break;
                }
            case InsertionMode.AFTER_AFTER_BODY:
                {
                    startTagAfterAfterBody(this, token);
                    break;
                }
            case InsertionMode.AFTER_AFTER_FRAMESET:
                {
                    startTagAfterAfterFrameset(this, token);
                    break;
                }
            default:
        }
    }
    /** @internal */ onEndTag(token) {
        this.skipNextNewLine = false;
        this.currentToken = token;
        if (this.currentNotInHTML) {
            endTagInForeignContent(this, token);
        } else {
            this._endTagOutsideForeignContent(token);
        }
    }
    /** @protected */ _endTagOutsideForeignContent(token) {
        switch(this.insertionMode){
            case InsertionMode.INITIAL:
                {
                    tokenInInitialMode(this, token);
                    break;
                }
            case InsertionMode.BEFORE_HTML:
                {
                    endTagBeforeHtml(this, token);
                    break;
                }
            case InsertionMode.BEFORE_HEAD:
                {
                    endTagBeforeHead(this, token);
                    break;
                }
            case InsertionMode.IN_HEAD:
                {
                    endTagInHead(this, token);
                    break;
                }
            case InsertionMode.IN_HEAD_NO_SCRIPT:
                {
                    endTagInHeadNoScript(this, token);
                    break;
                }
            case InsertionMode.AFTER_HEAD:
                {
                    endTagAfterHead(this, token);
                    break;
                }
            case InsertionMode.IN_BODY:
                {
                    endTagInBody(this, token);
                    break;
                }
            case InsertionMode.TEXT:
                {
                    endTagInText(this, token);
                    break;
                }
            case InsertionMode.IN_TABLE:
                {
                    endTagInTable(this, token);
                    break;
                }
            case InsertionMode.IN_TABLE_TEXT:
                {
                    tokenInTableText(this, token);
                    break;
                }
            case InsertionMode.IN_CAPTION:
                {
                    endTagInCaption(this, token);
                    break;
                }
            case InsertionMode.IN_COLUMN_GROUP:
                {
                    endTagInColumnGroup(this, token);
                    break;
                }
            case InsertionMode.IN_TABLE_BODY:
                {
                    endTagInTableBody(this, token);
                    break;
                }
            case InsertionMode.IN_ROW:
                {
                    endTagInRow(this, token);
                    break;
                }
            case InsertionMode.IN_CELL:
                {
                    endTagInCell(this, token);
                    break;
                }
            case InsertionMode.IN_SELECT:
                {
                    endTagInSelect(this, token);
                    break;
                }
            case InsertionMode.IN_SELECT_IN_TABLE:
                {
                    endTagInSelectInTable(this, token);
                    break;
                }
            case InsertionMode.IN_TEMPLATE:
                {
                    endTagInTemplate(this, token);
                    break;
                }
            case InsertionMode.AFTER_BODY:
                {
                    endTagAfterBody(this, token);
                    break;
                }
            case InsertionMode.IN_FRAMESET:
                {
                    endTagInFrameset(this, token);
                    break;
                }
            case InsertionMode.AFTER_FRAMESET:
                {
                    endTagAfterFrameset(this, token);
                    break;
                }
            case InsertionMode.AFTER_AFTER_BODY:
                {
                    tokenAfterAfterBody(this, token);
                    break;
                }
            default:
        }
    }
    /** @internal */ onEof(token) {
        switch(this.insertionMode){
            case InsertionMode.INITIAL:
                {
                    tokenInInitialMode(this, token);
                    break;
                }
            case InsertionMode.BEFORE_HTML:
                {
                    tokenBeforeHtml(this, token);
                    break;
                }
            case InsertionMode.BEFORE_HEAD:
                {
                    tokenBeforeHead(this, token);
                    break;
                }
            case InsertionMode.IN_HEAD:
                {
                    tokenInHead(this, token);
                    break;
                }
            case InsertionMode.IN_HEAD_NO_SCRIPT:
                {
                    tokenInHeadNoScript(this, token);
                    break;
                }
            case InsertionMode.AFTER_HEAD:
                {
                    tokenAfterHead(this, token);
                    break;
                }
            case InsertionMode.IN_BODY:
            case InsertionMode.IN_TABLE:
            case InsertionMode.IN_CAPTION:
            case InsertionMode.IN_COLUMN_GROUP:
            case InsertionMode.IN_TABLE_BODY:
            case InsertionMode.IN_ROW:
            case InsertionMode.IN_CELL:
            case InsertionMode.IN_SELECT:
            case InsertionMode.IN_SELECT_IN_TABLE:
                {
                    eofInBody(this, token);
                    break;
                }
            case InsertionMode.TEXT:
                {
                    eofInText(this, token);
                    break;
                }
            case InsertionMode.IN_TABLE_TEXT:
                {
                    tokenInTableText(this, token);
                    break;
                }
            case InsertionMode.IN_TEMPLATE:
                {
                    eofInTemplate(this, token);
                    break;
                }
            case InsertionMode.AFTER_BODY:
            case InsertionMode.IN_FRAMESET:
            case InsertionMode.AFTER_FRAMESET:
            case InsertionMode.AFTER_AFTER_BODY:
            case InsertionMode.AFTER_AFTER_FRAMESET:
                {
                    stopParsing(this, token);
                    break;
                }
            default:
        }
    }
    /** @internal */ onWhitespaceCharacter(token) {
        if (this.skipNextNewLine) {
            this.skipNextNewLine = false;
            if (token.chars.charCodeAt(0) === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CODE_POINTS"].LINE_FEED) {
                if (token.chars.length === 1) {
                    return;
                }
                token.chars = token.chars.substr(1);
            }
        }
        if (this.tokenizer.inForeignNode) {
            this._insertCharacters(token);
            return;
        }
        switch(this.insertionMode){
            case InsertionMode.IN_HEAD:
            case InsertionMode.IN_HEAD_NO_SCRIPT:
            case InsertionMode.AFTER_HEAD:
            case InsertionMode.TEXT:
            case InsertionMode.IN_COLUMN_GROUP:
            case InsertionMode.IN_SELECT:
            case InsertionMode.IN_SELECT_IN_TABLE:
            case InsertionMode.IN_FRAMESET:
            case InsertionMode.AFTER_FRAMESET:
                {
                    this._insertCharacters(token);
                    break;
                }
            case InsertionMode.IN_BODY:
            case InsertionMode.IN_CAPTION:
            case InsertionMode.IN_CELL:
            case InsertionMode.IN_TEMPLATE:
            case InsertionMode.AFTER_BODY:
            case InsertionMode.AFTER_AFTER_BODY:
            case InsertionMode.AFTER_AFTER_FRAMESET:
                {
                    whitespaceCharacterInBody(this, token);
                    break;
                }
            case InsertionMode.IN_TABLE:
            case InsertionMode.IN_TABLE_BODY:
            case InsertionMode.IN_ROW:
                {
                    characterInTable(this, token);
                    break;
                }
            case InsertionMode.IN_TABLE_TEXT:
                {
                    whitespaceCharacterInTableText(this, token);
                    break;
                }
            default:
        }
    }
}
//Adoption agency algorithm
//(see: http://www.whatwg.org/specs/web-apps/current-work/multipage/tree-construction.html#adoptionAgency)
//------------------------------------------------------------------
//Steps 5-8 of the algorithm
function aaObtainFormattingElementEntry(p, token) {
    let formattingElementEntry = p.activeFormattingElements.getElementEntryInScopeWithTagName(token.tagName);
    if (formattingElementEntry) {
        if (!p.openElements.contains(formattingElementEntry.element)) {
            p.activeFormattingElements.removeEntry(formattingElementEntry);
            formattingElementEntry = null;
        } else if (!p.openElements.hasInScope(token.tagID)) {
            formattingElementEntry = null;
        }
    } else {
        genericEndTagInBody(p, token);
    }
    return formattingElementEntry;
}
//Steps 9 and 10 of the algorithm
function aaObtainFurthestBlock(p, formattingElementEntry) {
    let furthestBlock = null;
    let idx = p.openElements.stackTop;
    for(; idx >= 0; idx--){
        const element = p.openElements.items[idx];
        if (element === formattingElementEntry.element) {
            break;
        }
        if (p._isSpecialElement(element, p.openElements.tagIDs[idx])) {
            furthestBlock = element;
        }
    }
    if (!furthestBlock) {
        p.openElements.shortenToLength(Math.max(idx, 0));
        p.activeFormattingElements.removeEntry(formattingElementEntry);
    }
    return furthestBlock;
}
//Step 13 of the algorithm
function aaInnerLoop(p, furthestBlock, formattingElement) {
    let lastElement = furthestBlock;
    let nextElement = p.openElements.getCommonAncestor(furthestBlock);
    for(let i = 0, element = nextElement; element !== formattingElement; i++, element = nextElement){
        //NOTE: store the next element for the next loop iteration (it may be deleted from the stack by step 9.5)
        nextElement = p.openElements.getCommonAncestor(element);
        const elementEntry = p.activeFormattingElements.getElementEntry(element);
        const counterOverflow = elementEntry && i >= AA_INNER_LOOP_ITER;
        const shouldRemoveFromOpenElements = !elementEntry || counterOverflow;
        if (shouldRemoveFromOpenElements) {
            if (counterOverflow) {
                p.activeFormattingElements.removeEntry(elementEntry);
            }
            p.openElements.remove(element);
        } else {
            element = aaRecreateElementFromEntry(p, elementEntry);
            if (lastElement === furthestBlock) {
                p.activeFormattingElements.bookmark = elementEntry;
            }
            p.treeAdapter.detachNode(lastElement);
            p.treeAdapter.appendChild(element, lastElement);
            lastElement = element;
        }
    }
    return lastElement;
}
//Step 13.7 of the algorithm
function aaRecreateElementFromEntry(p, elementEntry) {
    const ns = p.treeAdapter.getNamespaceURI(elementEntry.element);
    const newElement = p.treeAdapter.createElement(elementEntry.token.tagName, ns, elementEntry.token.attrs);
    p.openElements.replace(elementEntry.element, newElement);
    elementEntry.element = newElement;
    return newElement;
}
//Step 14 of the algorithm
function aaInsertLastNodeInCommonAncestor(p, commonAncestor, lastElement) {
    const tn = p.treeAdapter.getTagName(commonAncestor);
    const tid = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTagID"])(tn);
    if (p._isElementCausesFosterParenting(tid)) {
        p._fosterParentElement(lastElement);
    } else {
        const ns = p.treeAdapter.getNamespaceURI(commonAncestor);
        if (tid === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE && ns === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML) {
            commonAncestor = p.treeAdapter.getTemplateContent(commonAncestor);
        }
        p.treeAdapter.appendChild(commonAncestor, lastElement);
    }
}
//Steps 15-19 of the algorithm
function aaReplaceFormattingElement(p, furthestBlock, formattingElementEntry) {
    const ns = p.treeAdapter.getNamespaceURI(formattingElementEntry.element);
    const { token } = formattingElementEntry;
    const newElement = p.treeAdapter.createElement(token.tagName, ns, token.attrs);
    p._adoptNodes(furthestBlock, newElement);
    p.treeAdapter.appendChild(furthestBlock, newElement);
    p.activeFormattingElements.insertElementAfterBookmark(newElement, token);
    p.activeFormattingElements.removeEntry(formattingElementEntry);
    p.openElements.remove(formattingElementEntry.element);
    p.openElements.insertAfter(furthestBlock, newElement, token.tagID);
}
//Algorithm entry point
function callAdoptionAgency(p, token) {
    for(let i = 0; i < AA_OUTER_LOOP_ITER; i++){
        const formattingElementEntry = aaObtainFormattingElementEntry(p, token);
        if (!formattingElementEntry) {
            break;
        }
        const furthestBlock = aaObtainFurthestBlock(p, formattingElementEntry);
        if (!furthestBlock) {
            break;
        }
        p.activeFormattingElements.bookmark = formattingElementEntry;
        const lastElement = aaInnerLoop(p, furthestBlock, formattingElementEntry.element);
        const commonAncestor = p.openElements.getCommonAncestor(formattingElementEntry.element);
        p.treeAdapter.detachNode(lastElement);
        if (commonAncestor) aaInsertLastNodeInCommonAncestor(p, commonAncestor, lastElement);
        aaReplaceFormattingElement(p, furthestBlock, formattingElementEntry);
    }
}
//Generic token handlers
//------------------------------------------------------------------
function appendComment(p, token) {
    p._appendCommentNode(token, p.openElements.currentTmplContentOrNode);
}
function appendCommentToRootHtmlElement(p, token) {
    p._appendCommentNode(token, p.openElements.items[0]);
}
function appendCommentToDocument(p, token) {
    p._appendCommentNode(token, p.document);
}
function stopParsing(p, token) {
    p.stopped = true;
    // NOTE: Set end locations for elements that remain on the open element stack.
    if (token.location) {
        // NOTE: If we are not in a fragment, `html` and `body` will stay on the stack.
        // This is a problem, as we might overwrite their end position here.
        const target = p.fragmentContext ? 0 : 2;
        for(let i = p.openElements.stackTop; i >= target; i--){
            p._setEndLocation(p.openElements.items[i], token);
        }
        // Handle `html` and `body`
        if (!p.fragmentContext && p.openElements.stackTop >= 0) {
            const htmlElement = p.openElements.items[0];
            const htmlLocation = p.treeAdapter.getNodeSourceCodeLocation(htmlElement);
            if (htmlLocation && !htmlLocation.endTag) {
                p._setEndLocation(htmlElement, token);
                if (p.openElements.stackTop >= 1) {
                    const bodyElement = p.openElements.items[1];
                    const bodyLocation = p.treeAdapter.getNodeSourceCodeLocation(bodyElement);
                    if (bodyLocation && !bodyLocation.endTag) {
                        p._setEndLocation(bodyElement, token);
                    }
                }
            }
        }
    }
}
// The "initial" insertion mode
//------------------------------------------------------------------
function doctypeInInitialMode(p, token) {
    p._setDocumentType(token);
    const mode = token.forceQuirks ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DOCUMENT_MODE"].QUIRKS : __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$doctype$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getDocumentMode"](token);
    if (!__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$doctype$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isConforming"](token)) {
        p._err(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].nonConformingDoctype);
    }
    p.treeAdapter.setDocumentMode(p.document, mode);
    p.insertionMode = InsertionMode.BEFORE_HTML;
}
function tokenInInitialMode(p, token) {
    p._err(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].missingDoctype, true);
    p.treeAdapter.setDocumentMode(p.document, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DOCUMENT_MODE"].QUIRKS);
    p.insertionMode = InsertionMode.BEFORE_HTML;
    p._processToken(token);
}
// The "before html" insertion mode
//------------------------------------------------------------------
function startTagBeforeHtml(p, token) {
    if (token.tagID === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML) {
        p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
        p.insertionMode = InsertionMode.BEFORE_HEAD;
    } else {
        tokenBeforeHtml(p, token);
    }
}
function endTagBeforeHtml(p, token) {
    const tn = token.tagID;
    if (tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HEAD || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BODY || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BR) {
        tokenBeforeHtml(p, token);
    }
}
function tokenBeforeHtml(p, token) {
    p._insertFakeRootElement();
    p.insertionMode = InsertionMode.BEFORE_HEAD;
    p._processToken(token);
}
// The "before head" insertion mode
//------------------------------------------------------------------
function startTagBeforeHead(p, token) {
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML:
            {
                startTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HEAD:
            {
                p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
                p.headElement = p.openElements.current;
                p.insertionMode = InsertionMode.IN_HEAD;
                break;
            }
        default:
            {
                tokenBeforeHead(p, token);
            }
    }
}
function endTagBeforeHead(p, token) {
    const tn = token.tagID;
    if (tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HEAD || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BODY || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BR) {
        tokenBeforeHead(p, token);
    } else {
        p._err(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].endTagWithoutMatchingOpenElement);
    }
}
function tokenBeforeHead(p, token) {
    p._insertFakeElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].HEAD, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HEAD);
    p.headElement = p.openElements.current;
    p.insertionMode = InsertionMode.IN_HEAD;
    p._processToken(token);
}
// The "in head" insertion mode
//------------------------------------------------------------------
function startTagInHead(p, token) {
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML:
            {
                startTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BASE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BASEFONT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BGSOUND:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].LINK:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].META:
            {
                p._appendElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
                token.ackSelfClosing = true;
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TITLE:
            {
                p._switchToTextParsing(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tokenizer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenizerMode"].RCDATA);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NOSCRIPT:
            {
                if (p.options.scriptingEnabled) {
                    p._switchToTextParsing(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tokenizer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenizerMode"].RAWTEXT);
                } else {
                    p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
                    p.insertionMode = InsertionMode.IN_HEAD_NO_SCRIPT;
                }
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NOFRAMES:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].STYLE:
            {
                p._switchToTextParsing(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tokenizer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenizerMode"].RAWTEXT);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SCRIPT:
            {
                p._switchToTextParsing(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tokenizer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenizerMode"].SCRIPT_DATA);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE:
            {
                p._insertTemplate(token);
                p.activeFormattingElements.insertMarker();
                p.framesetOk = false;
                p.insertionMode = InsertionMode.IN_TEMPLATE;
                p.tmplInsertionModeStack.unshift(InsertionMode.IN_TEMPLATE);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HEAD:
            {
                p._err(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].misplacedStartTagForHeadElement);
                break;
            }
        default:
            {
                tokenInHead(p, token);
            }
    }
}
function endTagInHead(p, token) {
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HEAD:
            {
                p.openElements.pop();
                p.insertionMode = InsertionMode.AFTER_HEAD;
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BODY:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BR:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML:
            {
                tokenInHead(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE:
            {
                templateEndTagInHead(p, token);
                break;
            }
        default:
            {
                p._err(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].endTagWithoutMatchingOpenElement);
            }
    }
}
function templateEndTagInHead(p, token) {
    if (p.openElements.tmplCount > 0) {
        p.openElements.generateImpliedEndTagsThoroughly();
        if (p.openElements.currentTagId !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE) {
            p._err(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].closingOfElementWithOpenChildElements);
        }
        p.openElements.popUntilTagNamePopped(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE);
        p.activeFormattingElements.clearToLastMarker();
        p.tmplInsertionModeStack.shift();
        p._resetInsertionMode();
    } else {
        p._err(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].endTagWithoutMatchingOpenElement);
    }
}
function tokenInHead(p, token) {
    p.openElements.pop();
    p.insertionMode = InsertionMode.AFTER_HEAD;
    p._processToken(token);
}
// The "in head no script" insertion mode
//------------------------------------------------------------------
function startTagInHeadNoScript(p, token) {
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML:
            {
                startTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BASEFONT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BGSOUND:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HEAD:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].LINK:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].META:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NOFRAMES:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].STYLE:
            {
                startTagInHead(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NOSCRIPT:
            {
                p._err(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].nestedNoscriptInHead);
                break;
            }
        default:
            {
                tokenInHeadNoScript(p, token);
            }
    }
}
function endTagInHeadNoScript(p, token) {
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NOSCRIPT:
            {
                p.openElements.pop();
                p.insertionMode = InsertionMode.IN_HEAD;
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BR:
            {
                tokenInHeadNoScript(p, token);
                break;
            }
        default:
            {
                p._err(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].endTagWithoutMatchingOpenElement);
            }
    }
}
function tokenInHeadNoScript(p, token) {
    const errCode = token.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].EOF ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].openElementsLeftAfterEof : __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].disallowedContentInNoscriptInHead;
    p._err(token, errCode);
    p.openElements.pop();
    p.insertionMode = InsertionMode.IN_HEAD;
    p._processToken(token);
}
// The "after head" insertion mode
//------------------------------------------------------------------
function startTagAfterHead(p, token) {
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML:
            {
                startTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BODY:
            {
                p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
                p.framesetOk = false;
                p.insertionMode = InsertionMode.IN_BODY;
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FRAMESET:
            {
                p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
                p.insertionMode = InsertionMode.IN_FRAMESET;
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BASE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BASEFONT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BGSOUND:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].LINK:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].META:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NOFRAMES:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SCRIPT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].STYLE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TITLE:
            {
                p._err(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].abandonedHeadElementChild);
                p.openElements.push(p.headElement, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HEAD);
                startTagInHead(p, token);
                p.openElements.remove(p.headElement);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HEAD:
            {
                p._err(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].misplacedStartTagForHeadElement);
                break;
            }
        default:
            {
                tokenAfterHead(p, token);
            }
    }
}
function endTagAfterHead(p, token) {
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BODY:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BR:
            {
                tokenAfterHead(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE:
            {
                templateEndTagInHead(p, token);
                break;
            }
        default:
            {
                p._err(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].endTagWithoutMatchingOpenElement);
            }
    }
}
function tokenAfterHead(p, token) {
    p._insertFakeElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].BODY, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BODY);
    p.insertionMode = InsertionMode.IN_BODY;
    modeInBody(p, token);
}
// The "in body" insertion mode
//------------------------------------------------------------------
function modeInBody(p, token) {
    switch(token.type){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].CHARACTER:
            {
                characterInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].WHITESPACE_CHARACTER:
            {
                whitespaceCharacterInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].COMMENT:
            {
                appendComment(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].START_TAG:
            {
                startTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].END_TAG:
            {
                endTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].EOF:
            {
                eofInBody(p, token);
                break;
            }
        default:
    }
}
function whitespaceCharacterInBody(p, token) {
    p._reconstructActiveFormattingElements();
    p._insertCharacters(token);
}
function characterInBody(p, token) {
    p._reconstructActiveFormattingElements();
    p._insertCharacters(token);
    p.framesetOk = false;
}
function htmlStartTagInBody(p, token) {
    if (p.openElements.tmplCount === 0) {
        p.treeAdapter.adoptAttributes(p.openElements.items[0], token.attrs);
    }
}
function bodyStartTagInBody(p, token) {
    const bodyElement = p.openElements.tryPeekProperlyNestedBodyElement();
    if (bodyElement && p.openElements.tmplCount === 0) {
        p.framesetOk = false;
        p.treeAdapter.adoptAttributes(bodyElement, token.attrs);
    }
}
function framesetStartTagInBody(p, token) {
    const bodyElement = p.openElements.tryPeekProperlyNestedBodyElement();
    if (p.framesetOk && bodyElement) {
        p.treeAdapter.detachNode(bodyElement);
        p.openElements.popAllUpToHtmlElement();
        p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
        p.insertionMode = InsertionMode.IN_FRAMESET;
    }
}
function addressStartTagInBody(p, token) {
    if (p.openElements.hasInButtonScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].P)) {
        p._closePElement();
    }
    p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
}
function numberedHeaderStartTagInBody(p, token) {
    if (p.openElements.hasInButtonScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].P)) {
        p._closePElement();
    }
    if (p.openElements.currentTagId !== undefined && __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NUMBERED_HEADERS"].has(p.openElements.currentTagId)) {
        p.openElements.pop();
    }
    p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
}
function preStartTagInBody(p, token) {
    if (p.openElements.hasInButtonScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].P)) {
        p._closePElement();
    }
    p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    //NOTE: If the next token is a U+000A LINE FEED (LF) character token, then ignore that token and move
    //on to the next one. (Newlines at the start of pre blocks are ignored as an authoring convenience.)
    p.skipNextNewLine = true;
    p.framesetOk = false;
}
function formStartTagInBody(p, token) {
    const inTemplate = p.openElements.tmplCount > 0;
    if (!p.formElement || inTemplate) {
        if (p.openElements.hasInButtonScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].P)) {
            p._closePElement();
        }
        p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
        if (!inTemplate) {
            p.formElement = p.openElements.current;
        }
    }
}
function listItemStartTagInBody(p, token) {
    p.framesetOk = false;
    const tn = token.tagID;
    for(let i = p.openElements.stackTop; i >= 0; i--){
        const elementId = p.openElements.tagIDs[i];
        if (tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].LI && elementId === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].LI || (tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DD || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DT) && (elementId === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DD || elementId === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DT)) {
            p.openElements.generateImpliedEndTagsWithExclusion(elementId);
            p.openElements.popUntilTagNamePopped(elementId);
            break;
        }
        if (elementId !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].ADDRESS && elementId !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DIV && elementId !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].P && p._isSpecialElement(p.openElements.items[i], elementId)) {
            break;
        }
    }
    if (p.openElements.hasInButtonScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].P)) {
        p._closePElement();
    }
    p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
}
function plaintextStartTagInBody(p, token) {
    if (p.openElements.hasInButtonScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].P)) {
        p._closePElement();
    }
    p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    p.tokenizer.state = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tokenizer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenizerMode"].PLAINTEXT;
}
function buttonStartTagInBody(p, token) {
    if (p.openElements.hasInScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BUTTON)) {
        p.openElements.generateImpliedEndTags();
        p.openElements.popUntilTagNamePopped(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BUTTON);
    }
    p._reconstructActiveFormattingElements();
    p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    p.framesetOk = false;
}
function aStartTagInBody(p, token) {
    const activeElementEntry = p.activeFormattingElements.getElementEntryInScopeWithTagName(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].A);
    if (activeElementEntry) {
        callAdoptionAgency(p, token);
        p.openElements.remove(activeElementEntry.element);
        p.activeFormattingElements.removeEntry(activeElementEntry);
    }
    p._reconstructActiveFormattingElements();
    p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    p.activeFormattingElements.pushElement(p.openElements.current, token);
}
function bStartTagInBody(p, token) {
    p._reconstructActiveFormattingElements();
    p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    p.activeFormattingElements.pushElement(p.openElements.current, token);
}
function nobrStartTagInBody(p, token) {
    p._reconstructActiveFormattingElements();
    if (p.openElements.hasInScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NOBR)) {
        callAdoptionAgency(p, token);
        p._reconstructActiveFormattingElements();
    }
    p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    p.activeFormattingElements.pushElement(p.openElements.current, token);
}
function appletStartTagInBody(p, token) {
    p._reconstructActiveFormattingElements();
    p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    p.activeFormattingElements.insertMarker();
    p.framesetOk = false;
}
function tableStartTagInBody(p, token) {
    if (p.treeAdapter.getDocumentMode(p.document) !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DOCUMENT_MODE"].QUIRKS && p.openElements.hasInButtonScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].P)) {
        p._closePElement();
    }
    p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    p.framesetOk = false;
    p.insertionMode = InsertionMode.IN_TABLE;
}
function areaStartTagInBody(p, token) {
    p._reconstructActiveFormattingElements();
    p._appendElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    p.framesetOk = false;
    token.ackSelfClosing = true;
}
function isHiddenInput(token) {
    const inputType = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTokenAttr"])(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ATTRS"].TYPE);
    return inputType != null && inputType.toLowerCase() === HIDDEN_INPUT_TYPE;
}
function inputStartTagInBody(p, token) {
    p._reconstructActiveFormattingElements();
    p._appendElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    if (!isHiddenInput(token)) {
        p.framesetOk = false;
    }
    token.ackSelfClosing = true;
}
function paramStartTagInBody(p, token) {
    p._appendElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    token.ackSelfClosing = true;
}
function hrStartTagInBody(p, token) {
    if (p.openElements.hasInButtonScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].P)) {
        p._closePElement();
    }
    p._appendElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    p.framesetOk = false;
    token.ackSelfClosing = true;
}
function imageStartTagInBody(p, token) {
    token.tagName = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].IMG;
    token.tagID = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].IMG;
    areaStartTagInBody(p, token);
}
function textareaStartTagInBody(p, token) {
    p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    //NOTE: If the next token is a U+000A LINE FEED (LF) character token, then ignore that token and move
    //on to the next one. (Newlines at the start of textarea elements are ignored as an authoring convenience.)
    p.skipNextNewLine = true;
    p.tokenizer.state = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tokenizer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenizerMode"].RCDATA;
    p.originalInsertionMode = p.insertionMode;
    p.framesetOk = false;
    p.insertionMode = InsertionMode.TEXT;
}
function xmpStartTagInBody(p, token) {
    if (p.openElements.hasInButtonScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].P)) {
        p._closePElement();
    }
    p._reconstructActiveFormattingElements();
    p.framesetOk = false;
    p._switchToTextParsing(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tokenizer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenizerMode"].RAWTEXT);
}
function iframeStartTagInBody(p, token) {
    p.framesetOk = false;
    p._switchToTextParsing(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tokenizer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenizerMode"].RAWTEXT);
}
//NOTE: here we assume that we always act as a user agent with enabled plugins/frames, so we parse
//<noembed>/<noframes> as rawtext.
function rawTextStartTagInBody(p, token) {
    p._switchToTextParsing(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tokenizer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenizerMode"].RAWTEXT);
}
function selectStartTagInBody(p, token) {
    p._reconstructActiveFormattingElements();
    p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    p.framesetOk = false;
    p.insertionMode = p.insertionMode === InsertionMode.IN_TABLE || p.insertionMode === InsertionMode.IN_CAPTION || p.insertionMode === InsertionMode.IN_TABLE_BODY || p.insertionMode === InsertionMode.IN_ROW || p.insertionMode === InsertionMode.IN_CELL ? InsertionMode.IN_SELECT_IN_TABLE : InsertionMode.IN_SELECT;
}
function optgroupStartTagInBody(p, token) {
    if (p.openElements.currentTagId === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OPTION) {
        p.openElements.pop();
    }
    p._reconstructActiveFormattingElements();
    p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
}
function rbStartTagInBody(p, token) {
    if (p.openElements.hasInScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].RUBY)) {
        p.openElements.generateImpliedEndTags();
    }
    p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
}
function rtStartTagInBody(p, token) {
    if (p.openElements.hasInScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].RUBY)) {
        p.openElements.generateImpliedEndTagsWithExclusion(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].RTC);
    }
    p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
}
function mathStartTagInBody(p, token) {
    p._reconstructActiveFormattingElements();
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$foreign$2d$content$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["adjustTokenMathMLAttrs"](token);
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$foreign$2d$content$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["adjustTokenXMLAttrs"](token);
    if (token.selfClosing) {
        p._appendElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].MATHML);
    } else {
        p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].MATHML);
    }
    token.ackSelfClosing = true;
}
function svgStartTagInBody(p, token) {
    p._reconstructActiveFormattingElements();
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$foreign$2d$content$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["adjustTokenSVGAttrs"](token);
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$foreign$2d$content$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["adjustTokenXMLAttrs"](token);
    if (token.selfClosing) {
        p._appendElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].SVG);
    } else {
        p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].SVG);
    }
    token.ackSelfClosing = true;
}
function genericStartTagInBody(p, token) {
    p._reconstructActiveFormattingElements();
    p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
}
function startTagInBody(p, token) {
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].I:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].S:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].B:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].U:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].EM:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BIG:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CODE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FONT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SMALL:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].STRIKE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].STRONG:
            {
                bStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].A:
            {
                aStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].H1:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].H2:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].H3:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].H4:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].H5:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].H6:
            {
                numberedHeaderStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].P:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DL:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OL:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].UL:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DIV:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DIR:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NAV:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].MAIN:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].MENU:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].ASIDE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CENTER:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FIGURE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FOOTER:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HEADER:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HGROUP:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DIALOG:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DETAILS:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].ADDRESS:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].ARTICLE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SEARCH:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SECTION:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SUMMARY:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FIELDSET:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BLOCKQUOTE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FIGCAPTION:
            {
                addressStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].LI:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DD:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DT:
            {
                listItemStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BR:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].IMG:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].WBR:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].AREA:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].EMBED:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].KEYGEN:
            {
                areaStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HR:
            {
                hrStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].RB:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].RTC:
            {
                rbStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].RT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].RP:
            {
                rtStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].PRE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].LISTING:
            {
                preStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].XMP:
            {
                xmpStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SVG:
            {
                svgStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML:
            {
                htmlStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BASE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].LINK:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].META:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].STYLE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TITLE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SCRIPT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BGSOUND:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BASEFONT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE:
            {
                startTagInHead(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BODY:
            {
                bodyStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FORM:
            {
                formStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NOBR:
            {
                nobrStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].MATH:
            {
                mathStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE:
            {
                tableStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].INPUT:
            {
                inputStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].PARAM:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TRACK:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SOURCE:
            {
                paramStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].IMAGE:
            {
                imageStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BUTTON:
            {
                buttonStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].APPLET:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OBJECT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].MARQUEE:
            {
                appletStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].IFRAME:
            {
                iframeStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SELECT:
            {
                selectStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OPTION:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OPTGROUP:
            {
                optgroupStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NOEMBED:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NOFRAMES:
            {
                rawTextStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FRAMESET:
            {
                framesetStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEXTAREA:
            {
                textareaStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NOSCRIPT:
            {
                if (p.options.scriptingEnabled) {
                    rawTextStartTagInBody(p, token);
                } else {
                    genericStartTagInBody(p, token);
                }
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].PLAINTEXT:
            {
                plaintextStartTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COL:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TH:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TD:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HEAD:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FRAME:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TBODY:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TFOOT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].THEAD:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CAPTION:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COLGROUP:
            {
                break;
            }
        default:
            {
                genericStartTagInBody(p, token);
            }
    }
}
function bodyEndTagInBody(p, token) {
    if (p.openElements.hasInScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BODY)) {
        p.insertionMode = InsertionMode.AFTER_BODY;
        //NOTE: <body> is never popped from the stack, so we need to updated
        //the end location explicitly.
        if (p.options.sourceCodeLocationInfo) {
            const bodyElement = p.openElements.tryPeekProperlyNestedBodyElement();
            if (bodyElement) {
                p._setEndLocation(bodyElement, token);
            }
        }
    }
}
function htmlEndTagInBody(p, token) {
    if (p.openElements.hasInScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BODY)) {
        p.insertionMode = InsertionMode.AFTER_BODY;
        endTagAfterBody(p, token);
    }
}
function addressEndTagInBody(p, token) {
    const tn = token.tagID;
    if (p.openElements.hasInScope(tn)) {
        p.openElements.generateImpliedEndTags();
        p.openElements.popUntilTagNamePopped(tn);
    }
}
function formEndTagInBody(p) {
    const inTemplate = p.openElements.tmplCount > 0;
    const { formElement } = p;
    if (!inTemplate) {
        p.formElement = null;
    }
    if ((formElement || inTemplate) && p.openElements.hasInScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FORM)) {
        p.openElements.generateImpliedEndTags();
        if (inTemplate) {
            p.openElements.popUntilTagNamePopped(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FORM);
        } else if (formElement) {
            p.openElements.remove(formElement);
        }
    }
}
function pEndTagInBody(p) {
    if (!p.openElements.hasInButtonScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].P)) {
        p._insertFakeElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].P, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].P);
    }
    p._closePElement();
}
function liEndTagInBody(p) {
    if (p.openElements.hasInListItemScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].LI)) {
        p.openElements.generateImpliedEndTagsWithExclusion(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].LI);
        p.openElements.popUntilTagNamePopped(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].LI);
    }
}
function ddEndTagInBody(p, token) {
    const tn = token.tagID;
    if (p.openElements.hasInScope(tn)) {
        p.openElements.generateImpliedEndTagsWithExclusion(tn);
        p.openElements.popUntilTagNamePopped(tn);
    }
}
function numberedHeaderEndTagInBody(p) {
    if (p.openElements.hasNumberedHeaderInScope()) {
        p.openElements.generateImpliedEndTags();
        p.openElements.popUntilNumberedHeaderPopped();
    }
}
function appletEndTagInBody(p, token) {
    const tn = token.tagID;
    if (p.openElements.hasInScope(tn)) {
        p.openElements.generateImpliedEndTags();
        p.openElements.popUntilTagNamePopped(tn);
        p.activeFormattingElements.clearToLastMarker();
    }
}
function brEndTagInBody(p) {
    p._reconstructActiveFormattingElements();
    p._insertFakeElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].BR, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BR);
    p.openElements.pop();
    p.framesetOk = false;
}
function genericEndTagInBody(p, token) {
    const tn = token.tagName;
    const tid = token.tagID;
    for(let i = p.openElements.stackTop; i > 0; i--){
        const element = p.openElements.items[i];
        const elementId = p.openElements.tagIDs[i];
        // Compare the tag name here, as the tag might not be a known tag with an ID.
        if (tid === elementId && (tid !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].UNKNOWN || p.treeAdapter.getTagName(element) === tn)) {
            p.openElements.generateImpliedEndTagsWithExclusion(tid);
            if (p.openElements.stackTop >= i) p.openElements.shortenToLength(i);
            break;
        }
        if (p._isSpecialElement(element, elementId)) {
            break;
        }
    }
}
function endTagInBody(p, token) {
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].A:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].B:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].I:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].S:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].U:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].EM:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BIG:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CODE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FONT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NOBR:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SMALL:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].STRIKE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].STRONG:
            {
                callAdoptionAgency(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].P:
            {
                pEndTagInBody(p);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DL:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].UL:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OL:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DIR:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DIV:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NAV:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].PRE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].MAIN:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].MENU:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].ASIDE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BUTTON:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CENTER:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FIGURE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FOOTER:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HEADER:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HGROUP:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DIALOG:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].ADDRESS:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].ARTICLE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DETAILS:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SEARCH:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SECTION:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SUMMARY:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].LISTING:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FIELDSET:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BLOCKQUOTE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FIGCAPTION:
            {
                addressEndTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].LI:
            {
                liEndTagInBody(p);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DD:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].DT:
            {
                ddEndTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].H1:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].H2:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].H3:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].H4:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].H5:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].H6:
            {
                numberedHeaderEndTagInBody(p);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BR:
            {
                brEndTagInBody(p);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BODY:
            {
                bodyEndTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML:
            {
                htmlEndTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FORM:
            {
                formEndTagInBody(p);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].APPLET:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OBJECT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].MARQUEE:
            {
                appletEndTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE:
            {
                templateEndTagInHead(p, token);
                break;
            }
        default:
            {
                genericEndTagInBody(p, token);
            }
    }
}
function eofInBody(p, token) {
    if (p.tmplInsertionModeStack.length > 0) {
        eofInTemplate(p, token);
    } else {
        stopParsing(p, token);
    }
}
// The "text" insertion mode
//------------------------------------------------------------------
function endTagInText(p, token) {
    var _a;
    if (token.tagID === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SCRIPT) {
        (_a = p.scriptHandler) === null || _a === void 0 ? void 0 : _a.call(p, p.openElements.current);
    }
    p.openElements.pop();
    p.insertionMode = p.originalInsertionMode;
}
function eofInText(p, token) {
    p._err(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ERR"].eofInElementThatCanContainOnlyText);
    p.openElements.pop();
    p.insertionMode = p.originalInsertionMode;
    p.onEof(token);
}
// The "in table" insertion mode
//------------------------------------------------------------------
function characterInTable(p, token) {
    if (p.openElements.currentTagId !== undefined && TABLE_STRUCTURE_TAGS.has(p.openElements.currentTagId)) {
        p.pendingCharacterTokens.length = 0;
        p.hasNonWhitespacePendingCharacterToken = false;
        p.originalInsertionMode = p.insertionMode;
        p.insertionMode = InsertionMode.IN_TABLE_TEXT;
        switch(token.type){
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].CHARACTER:
                {
                    characterInTableText(p, token);
                    break;
                }
            case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TokenType"].WHITESPACE_CHARACTER:
                {
                    whitespaceCharacterInTableText(p, token);
                    break;
                }
        }
    } else {
        tokenInTable(p, token);
    }
}
function captionStartTagInTable(p, token) {
    p.openElements.clearBackToTableContext();
    p.activeFormattingElements.insertMarker();
    p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    p.insertionMode = InsertionMode.IN_CAPTION;
}
function colgroupStartTagInTable(p, token) {
    p.openElements.clearBackToTableContext();
    p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    p.insertionMode = InsertionMode.IN_COLUMN_GROUP;
}
function colStartTagInTable(p, token) {
    p.openElements.clearBackToTableContext();
    p._insertFakeElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].COLGROUP, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COLGROUP);
    p.insertionMode = InsertionMode.IN_COLUMN_GROUP;
    startTagInColumnGroup(p, token);
}
function tbodyStartTagInTable(p, token) {
    p.openElements.clearBackToTableContext();
    p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    p.insertionMode = InsertionMode.IN_TABLE_BODY;
}
function tdStartTagInTable(p, token) {
    p.openElements.clearBackToTableContext();
    p._insertFakeElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].TBODY, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TBODY);
    p.insertionMode = InsertionMode.IN_TABLE_BODY;
    startTagInTableBody(p, token);
}
function tableStartTagInTable(p, token) {
    if (p.openElements.hasInTableScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE)) {
        p.openElements.popUntilTagNamePopped(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE);
        p._resetInsertionMode();
        p._processStartTag(token);
    }
}
function inputStartTagInTable(p, token) {
    if (isHiddenInput(token)) {
        p._appendElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
    } else {
        tokenInTable(p, token);
    }
    token.ackSelfClosing = true;
}
function formStartTagInTable(p, token) {
    if (!p.formElement && p.openElements.tmplCount === 0) {
        p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
        p.formElement = p.openElements.current;
        p.openElements.pop();
    }
}
function startTagInTable(p, token) {
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TD:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TH:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR:
            {
                tdStartTagInTable(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].STYLE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SCRIPT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE:
            {
                startTagInHead(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COL:
            {
                colStartTagInTable(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FORM:
            {
                formStartTagInTable(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE:
            {
                tableStartTagInTable(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TBODY:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TFOOT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].THEAD:
            {
                tbodyStartTagInTable(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].INPUT:
            {
                inputStartTagInTable(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CAPTION:
            {
                captionStartTagInTable(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COLGROUP:
            {
                colgroupStartTagInTable(p, token);
                break;
            }
        default:
            {
                tokenInTable(p, token);
            }
    }
}
function endTagInTable(p, token) {
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE:
            {
                if (p.openElements.hasInTableScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE)) {
                    p.openElements.popUntilTagNamePopped(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE);
                    p._resetInsertionMode();
                }
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE:
            {
                templateEndTagInHead(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BODY:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CAPTION:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COL:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COLGROUP:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TBODY:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TD:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TFOOT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TH:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].THEAD:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR:
            {
                break;
            }
        default:
            {
                tokenInTable(p, token);
            }
    }
}
function tokenInTable(p, token) {
    const savedFosterParentingState = p.fosterParentingEnabled;
    p.fosterParentingEnabled = true;
    // Process token in `In Body` mode
    modeInBody(p, token);
    p.fosterParentingEnabled = savedFosterParentingState;
}
// The "in table text" insertion mode
//------------------------------------------------------------------
function whitespaceCharacterInTableText(p, token) {
    p.pendingCharacterTokens.push(token);
}
function characterInTableText(p, token) {
    p.pendingCharacterTokens.push(token);
    p.hasNonWhitespacePendingCharacterToken = true;
}
function tokenInTableText(p, token) {
    let i = 0;
    if (p.hasNonWhitespacePendingCharacterToken) {
        for(; i < p.pendingCharacterTokens.length; i++){
            tokenInTable(p, p.pendingCharacterTokens[i]);
        }
    } else {
        for(; i < p.pendingCharacterTokens.length; i++){
            p._insertCharacters(p.pendingCharacterTokens[i]);
        }
    }
    p.insertionMode = p.originalInsertionMode;
    p._processToken(token);
}
// The "in caption" insertion mode
//------------------------------------------------------------------
const TABLE_VOID_ELEMENTS = new Set([
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CAPTION,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COL,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COLGROUP,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TBODY,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TD,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TFOOT,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TH,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].THEAD,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR
]);
function startTagInCaption(p, token) {
    const tn = token.tagID;
    if (TABLE_VOID_ELEMENTS.has(tn)) {
        if (p.openElements.hasInTableScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CAPTION)) {
            p.openElements.generateImpliedEndTags();
            p.openElements.popUntilTagNamePopped(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CAPTION);
            p.activeFormattingElements.clearToLastMarker();
            p.insertionMode = InsertionMode.IN_TABLE;
            startTagInTable(p, token);
        }
    } else {
        startTagInBody(p, token);
    }
}
function endTagInCaption(p, token) {
    const tn = token.tagID;
    switch(tn){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CAPTION:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE:
            {
                if (p.openElements.hasInTableScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CAPTION)) {
                    p.openElements.generateImpliedEndTags();
                    p.openElements.popUntilTagNamePopped(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CAPTION);
                    p.activeFormattingElements.clearToLastMarker();
                    p.insertionMode = InsertionMode.IN_TABLE;
                    if (tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE) {
                        endTagInTable(p, token);
                    }
                }
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BODY:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COL:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COLGROUP:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TBODY:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TD:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TFOOT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TH:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].THEAD:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR:
            {
                break;
            }
        default:
            {
                endTagInBody(p, token);
            }
    }
}
// The "in column group" insertion mode
//------------------------------------------------------------------
function startTagInColumnGroup(p, token) {
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML:
            {
                startTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COL:
            {
                p._appendElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
                token.ackSelfClosing = true;
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE:
            {
                startTagInHead(p, token);
                break;
            }
        default:
            {
                tokenInColumnGroup(p, token);
            }
    }
}
function endTagInColumnGroup(p, token) {
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COLGROUP:
            {
                if (p.openElements.currentTagId === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COLGROUP) {
                    p.openElements.pop();
                    p.insertionMode = InsertionMode.IN_TABLE;
                }
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE:
            {
                templateEndTagInHead(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COL:
            {
                break;
            }
        default:
            {
                tokenInColumnGroup(p, token);
            }
    }
}
function tokenInColumnGroup(p, token) {
    if (p.openElements.currentTagId === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COLGROUP) {
        p.openElements.pop();
        p.insertionMode = InsertionMode.IN_TABLE;
        p._processToken(token);
    }
}
// The "in table body" insertion mode
//------------------------------------------------------------------
function startTagInTableBody(p, token) {
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR:
            {
                p.openElements.clearBackToTableBodyContext();
                p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
                p.insertionMode = InsertionMode.IN_ROW;
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TH:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TD:
            {
                p.openElements.clearBackToTableBodyContext();
                p._insertFakeElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].TR, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR);
                p.insertionMode = InsertionMode.IN_ROW;
                startTagInRow(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CAPTION:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COL:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COLGROUP:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TBODY:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TFOOT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].THEAD:
            {
                if (p.openElements.hasTableBodyContextInTableScope()) {
                    p.openElements.clearBackToTableBodyContext();
                    p.openElements.pop();
                    p.insertionMode = InsertionMode.IN_TABLE;
                    startTagInTable(p, token);
                }
                break;
            }
        default:
            {
                startTagInTable(p, token);
            }
    }
}
function endTagInTableBody(p, token) {
    const tn = token.tagID;
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TBODY:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TFOOT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].THEAD:
            {
                if (p.openElements.hasInTableScope(tn)) {
                    p.openElements.clearBackToTableBodyContext();
                    p.openElements.pop();
                    p.insertionMode = InsertionMode.IN_TABLE;
                }
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE:
            {
                if (p.openElements.hasTableBodyContextInTableScope()) {
                    p.openElements.clearBackToTableBodyContext();
                    p.openElements.pop();
                    p.insertionMode = InsertionMode.IN_TABLE;
                    endTagInTable(p, token);
                }
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BODY:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CAPTION:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COL:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COLGROUP:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TD:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TH:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR:
            {
                break;
            }
        default:
            {
                endTagInTable(p, token);
            }
    }
}
// The "in row" insertion mode
//------------------------------------------------------------------
function startTagInRow(p, token) {
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TH:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TD:
            {
                p.openElements.clearBackToTableRowContext();
                p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
                p.insertionMode = InsertionMode.IN_CELL;
                p.activeFormattingElements.insertMarker();
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CAPTION:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COL:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COLGROUP:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TBODY:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TFOOT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].THEAD:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR:
            {
                if (p.openElements.hasInTableScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR)) {
                    p.openElements.clearBackToTableRowContext();
                    p.openElements.pop();
                    p.insertionMode = InsertionMode.IN_TABLE_BODY;
                    startTagInTableBody(p, token);
                }
                break;
            }
        default:
            {
                startTagInTable(p, token);
            }
    }
}
function endTagInRow(p, token) {
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR:
            {
                if (p.openElements.hasInTableScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR)) {
                    p.openElements.clearBackToTableRowContext();
                    p.openElements.pop();
                    p.insertionMode = InsertionMode.IN_TABLE_BODY;
                }
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE:
            {
                if (p.openElements.hasInTableScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR)) {
                    p.openElements.clearBackToTableRowContext();
                    p.openElements.pop();
                    p.insertionMode = InsertionMode.IN_TABLE_BODY;
                    endTagInTableBody(p, token);
                }
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TBODY:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TFOOT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].THEAD:
            {
                if (p.openElements.hasInTableScope(token.tagID) || p.openElements.hasInTableScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR)) {
                    p.openElements.clearBackToTableRowContext();
                    p.openElements.pop();
                    p.insertionMode = InsertionMode.IN_TABLE_BODY;
                    endTagInTableBody(p, token);
                }
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BODY:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CAPTION:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COL:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COLGROUP:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TD:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TH:
            {
                break;
            }
        default:
            {
                endTagInTable(p, token);
            }
    }
}
// The "in cell" insertion mode
//------------------------------------------------------------------
function startTagInCell(p, token) {
    const tn = token.tagID;
    if (TABLE_VOID_ELEMENTS.has(tn)) {
        if (p.openElements.hasInTableScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TD) || p.openElements.hasInTableScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TH)) {
            p._closeTableCell();
            startTagInRow(p, token);
        }
    } else {
        startTagInBody(p, token);
    }
}
function endTagInCell(p, token) {
    const tn = token.tagID;
    switch(tn){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TD:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TH:
            {
                if (p.openElements.hasInTableScope(tn)) {
                    p.openElements.generateImpliedEndTags();
                    p.openElements.popUntilTagNamePopped(tn);
                    p.activeFormattingElements.clearToLastMarker();
                    p.insertionMode = InsertionMode.IN_ROW;
                }
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TBODY:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TFOOT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].THEAD:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR:
            {
                if (p.openElements.hasInTableScope(tn)) {
                    p._closeTableCell();
                    endTagInRow(p, token);
                }
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BODY:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CAPTION:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COL:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COLGROUP:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML:
            {
                break;
            }
        default:
            {
                endTagInBody(p, token);
            }
    }
}
// The "in select" insertion mode
//------------------------------------------------------------------
function startTagInSelect(p, token) {
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML:
            {
                startTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OPTION:
            {
                if (p.openElements.currentTagId === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OPTION) {
                    p.openElements.pop();
                }
                p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OPTGROUP:
            {
                if (p.openElements.currentTagId === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OPTION) {
                    p.openElements.pop();
                }
                if (p.openElements.currentTagId === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OPTGROUP) {
                    p.openElements.pop();
                }
                p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HR:
            {
                if (p.openElements.currentTagId === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OPTION) {
                    p.openElements.pop();
                }
                if (p.openElements.currentTagId === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OPTGROUP) {
                    p.openElements.pop();
                }
                p._appendElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
                token.ackSelfClosing = true;
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].INPUT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].KEYGEN:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEXTAREA:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SELECT:
            {
                if (p.openElements.hasInSelectScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SELECT)) {
                    p.openElements.popUntilTagNamePopped(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SELECT);
                    p._resetInsertionMode();
                    if (token.tagID !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SELECT) {
                        p._processStartTag(token);
                    }
                }
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SCRIPT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE:
            {
                startTagInHead(p, token);
                break;
            }
        default:
    }
}
function endTagInSelect(p, token) {
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OPTGROUP:
            {
                if (p.openElements.stackTop > 0 && p.openElements.currentTagId === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OPTION && p.openElements.tagIDs[p.openElements.stackTop - 1] === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OPTGROUP) {
                    p.openElements.pop();
                }
                if (p.openElements.currentTagId === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OPTGROUP) {
                    p.openElements.pop();
                }
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OPTION:
            {
                if (p.openElements.currentTagId === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].OPTION) {
                    p.openElements.pop();
                }
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SELECT:
            {
                if (p.openElements.hasInSelectScope(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SELECT)) {
                    p.openElements.popUntilTagNamePopped(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SELECT);
                    p._resetInsertionMode();
                }
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE:
            {
                templateEndTagInHead(p, token);
                break;
            }
        default:
    }
}
// The "in select in table" insertion mode
//------------------------------------------------------------------
function startTagInSelectInTable(p, token) {
    const tn = token.tagID;
    if (tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CAPTION || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TBODY || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TFOOT || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].THEAD || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TD || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TH) {
        p.openElements.popUntilTagNamePopped(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SELECT);
        p._resetInsertionMode();
        p._processStartTag(token);
    } else {
        startTagInSelect(p, token);
    }
}
function endTagInSelectInTable(p, token) {
    const tn = token.tagID;
    if (tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CAPTION || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TABLE || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TBODY || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TFOOT || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].THEAD || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TD || tn === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TH) {
        if (p.openElements.hasInTableScope(tn)) {
            p.openElements.popUntilTagNamePopped(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SELECT);
            p._resetInsertionMode();
            p.onEndTag(token);
        }
    } else {
        endTagInSelect(p, token);
    }
}
// The "in template" insertion mode
//------------------------------------------------------------------
function startTagInTemplate(p, token) {
    switch(token.tagID){
        // First, handle tags that can start without a mode change
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BASE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BASEFONT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BGSOUND:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].LINK:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].META:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NOFRAMES:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].SCRIPT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].STYLE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TITLE:
            {
                startTagInHead(p, token);
                break;
            }
        // Re-process the token in the appropriate mode
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].CAPTION:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COLGROUP:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TBODY:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TFOOT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].THEAD:
            {
                p.tmplInsertionModeStack[0] = InsertionMode.IN_TABLE;
                p.insertionMode = InsertionMode.IN_TABLE;
                startTagInTable(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].COL:
            {
                p.tmplInsertionModeStack[0] = InsertionMode.IN_COLUMN_GROUP;
                p.insertionMode = InsertionMode.IN_COLUMN_GROUP;
                startTagInColumnGroup(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TR:
            {
                p.tmplInsertionModeStack[0] = InsertionMode.IN_TABLE_BODY;
                p.insertionMode = InsertionMode.IN_TABLE_BODY;
                startTagInTableBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TD:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TH:
            {
                p.tmplInsertionModeStack[0] = InsertionMode.IN_ROW;
                p.insertionMode = InsertionMode.IN_ROW;
                startTagInRow(p, token);
                break;
            }
        default:
            {
                p.tmplInsertionModeStack[0] = InsertionMode.IN_BODY;
                p.insertionMode = InsertionMode.IN_BODY;
                startTagInBody(p, token);
            }
    }
}
function endTagInTemplate(p, token) {
    if (token.tagID === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE) {
        templateEndTagInHead(p, token);
    }
}
function eofInTemplate(p, token) {
    if (p.openElements.tmplCount > 0) {
        p.openElements.popUntilTagNamePopped(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].TEMPLATE);
        p.activeFormattingElements.clearToLastMarker();
        p.tmplInsertionModeStack.shift();
        p._resetInsertionMode();
        p.onEof(token);
    } else {
        stopParsing(p, token);
    }
}
// The "after body" insertion mode
//------------------------------------------------------------------
function startTagAfterBody(p, token) {
    if (token.tagID === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML) {
        startTagInBody(p, token);
    } else {
        tokenAfterBody(p, token);
    }
}
function endTagAfterBody(p, token) {
    var _a;
    if (token.tagID === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML) {
        if (!p.fragmentContext) {
            p.insertionMode = InsertionMode.AFTER_AFTER_BODY;
        }
        //NOTE: <html> is never popped from the stack, so we need to updated
        //the end location explicitly.
        if (p.options.sourceCodeLocationInfo && p.openElements.tagIDs[0] === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML) {
            p._setEndLocation(p.openElements.items[0], token);
            // Update the body element, if it doesn't have an end tag
            const bodyElement = p.openElements.items[1];
            if (bodyElement && !((_a = p.treeAdapter.getNodeSourceCodeLocation(bodyElement)) === null || _a === void 0 ? void 0 : _a.endTag)) {
                p._setEndLocation(bodyElement, token);
            }
        }
    } else {
        tokenAfterBody(p, token);
    }
}
function tokenAfterBody(p, token) {
    p.insertionMode = InsertionMode.IN_BODY;
    modeInBody(p, token);
}
// The "in frameset" insertion mode
//------------------------------------------------------------------
function startTagInFrameset(p, token) {
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML:
            {
                startTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FRAMESET:
            {
                p._insertElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FRAME:
            {
                p._appendElement(token, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML);
                token.ackSelfClosing = true;
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NOFRAMES:
            {
                startTagInHead(p, token);
                break;
            }
        default:
    }
}
function endTagInFrameset(p, token) {
    if (token.tagID === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FRAMESET && !p.openElements.isRootHtmlElementCurrent()) {
        p.openElements.pop();
        if (!p.fragmentContext && p.openElements.currentTagId !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].FRAMESET) {
            p.insertionMode = InsertionMode.AFTER_FRAMESET;
        }
    }
}
// The "after frameset" insertion mode
//------------------------------------------------------------------
function startTagAfterFrameset(p, token) {
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML:
            {
                startTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NOFRAMES:
            {
                startTagInHead(p, token);
                break;
            }
        default:
    }
}
function endTagAfterFrameset(p, token) {
    if (token.tagID === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML) {
        p.insertionMode = InsertionMode.AFTER_AFTER_FRAMESET;
    }
}
// The "after after body" insertion mode
//------------------------------------------------------------------
function startTagAfterAfterBody(p, token) {
    if (token.tagID === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML) {
        startTagInBody(p, token);
    } else {
        tokenAfterAfterBody(p, token);
    }
}
function tokenAfterAfterBody(p, token) {
    p.insertionMode = InsertionMode.IN_BODY;
    modeInBody(p, token);
}
// The "after after frameset" insertion mode
//------------------------------------------------------------------
function startTagAfterAfterFrameset(p, token) {
    switch(token.tagID){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].HTML:
            {
                startTagInBody(p, token);
                break;
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].NOFRAMES:
            {
                startTagInHead(p, token);
                break;
            }
        default:
    }
}
// The rules for parsing tokens in foreign content
//------------------------------------------------------------------
function nullCharacterInForeignContent(p, token) {
    token.chars = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$unicode$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["REPLACEMENT_CHARACTER"];
    p._insertCharacters(token);
}
function characterInForeignContent(p, token) {
    p._insertCharacters(token);
    p.framesetOk = false;
}
function popUntilHtmlOrIntegrationPoint(p) {
    while(p.treeAdapter.getNamespaceURI(p.openElements.current) !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML && p.openElements.currentTagId !== undefined && !p._isIntegrationPoint(p.openElements.currentTagId, p.openElements.current)){
        p.openElements.pop();
    }
}
function startTagInForeignContent(p, token) {
    if (__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$foreign$2d$content$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["causesExit"](token)) {
        popUntilHtmlOrIntegrationPoint(p);
        p._startTagOutsideForeignContent(token);
    } else {
        const current = p._getAdjustedCurrentElement();
        const currentNs = p.treeAdapter.getNamespaceURI(current);
        if (currentNs === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].MATHML) {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$foreign$2d$content$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["adjustTokenMathMLAttrs"](token);
        } else if (currentNs === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].SVG) {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$foreign$2d$content$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["adjustTokenSVGTagName"](token);
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$foreign$2d$content$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["adjustTokenSVGAttrs"](token);
        }
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$foreign$2d$content$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["adjustTokenXMLAttrs"](token);
        if (token.selfClosing) {
            p._appendElement(token, currentNs);
        } else {
            p._insertElement(token, currentNs);
        }
        token.ackSelfClosing = true;
    }
}
function endTagInForeignContent(p, token) {
    if (token.tagID === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].P || token.tagID === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_ID"].BR) {
        popUntilHtmlOrIntegrationPoint(p);
        p._endTagOutsideForeignContent(token);
        return;
    }
    for(let i = p.openElements.stackTop; i > 0; i--){
        const element = p.openElements.items[i];
        if (p.treeAdapter.getNamespaceURI(element) === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML) {
            p._endTagOutsideForeignContent(token);
            break;
        }
        const tagName = p.treeAdapter.getTagName(element);
        if (tagName.toLowerCase() === token.tagName) {
            //NOTE: update the token tag name for `_setEndLocation`.
            token.tagName = tagName;
            p.openElements.shortenToLength(i);
            break;
        }
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/parse5/dist/serializer/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "serialize",
    ()=>serialize,
    "serializeOuter",
    ()=>serializeOuter
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/html.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$entities$2f$dist$2f$esm$2f$escape$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/entities/dist/esm/escape.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tree$2d$adapters$2f$default$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/tree-adapters/default.js [app-client] (ecmascript)");
;
;
;
// Sets
const VOID_ELEMENTS = new Set([
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].AREA,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].BASE,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].BASEFONT,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].BGSOUND,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].BR,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].COL,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].EMBED,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].FRAME,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].HR,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].IMG,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].INPUT,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].KEYGEN,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].LINK,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].META,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].PARAM,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].SOURCE,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].TRACK,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].WBR
]);
function isVoidElement(node, options) {
    return options.treeAdapter.isElementNode(node) && options.treeAdapter.getNamespaceURI(node) === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML && VOID_ELEMENTS.has(options.treeAdapter.getTagName(node));
}
const defaultOpts = {
    treeAdapter: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tree$2d$adapters$2f$default$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["defaultTreeAdapter"],
    scriptingEnabled: true
};
function serialize(node, options) {
    const opts = {
        ...defaultOpts,
        ...options
    };
    if (isVoidElement(node, opts)) {
        return '';
    }
    return serializeChildNodes(node, opts);
}
function serializeOuter(node, options) {
    const opts = {
        ...defaultOpts,
        ...options
    };
    return serializeNode(node, opts);
}
function serializeChildNodes(parentNode, options) {
    let html = '';
    // Get container of the child nodes
    const container = options.treeAdapter.isElementNode(parentNode) && options.treeAdapter.getTagName(parentNode) === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TAG_NAMES"].TEMPLATE && options.treeAdapter.getNamespaceURI(parentNode) === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML ? options.treeAdapter.getTemplateContent(parentNode) : parentNode;
    const childNodes = options.treeAdapter.getChildNodes(container);
    if (childNodes) {
        for (const currentNode of childNodes){
            html += serializeNode(currentNode, options);
        }
    }
    return html;
}
function serializeNode(node, options) {
    if (options.treeAdapter.isElementNode(node)) {
        return serializeElement(node, options);
    }
    if (options.treeAdapter.isTextNode(node)) {
        return serializeTextNode(node, options);
    }
    if (options.treeAdapter.isCommentNode(node)) {
        return serializeCommentNode(node, options);
    }
    if (options.treeAdapter.isDocumentTypeNode(node)) {
        return serializeDocumentTypeNode(node, options);
    }
    // Return an empty string for unknown nodes
    return '';
}
function serializeElement(node, options) {
    const tn = options.treeAdapter.getTagName(node);
    return `<${tn}${serializeAttributes(node, options)}>${isVoidElement(node, options) ? '' : `${serializeChildNodes(node, options)}</${tn}>`}`;
}
function serializeAttributes(node, { treeAdapter }) {
    let html = '';
    for (const attr of treeAdapter.getAttrList(node)){
        html += ' ';
        if (attr.namespace) {
            switch(attr.namespace){
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].XML:
                    {
                        html += `xml:${attr.name}`;
                        break;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].XMLNS:
                    {
                        if (attr.name !== 'xmlns') {
                            html += 'xmlns:';
                        }
                        html += attr.name;
                        break;
                    }
                case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].XLINK:
                    {
                        html += `xlink:${attr.name}`;
                        break;
                    }
                default:
                    {
                        html += `${attr.prefix}:${attr.name}`;
                    }
            }
        } else {
            html += attr.name;
        }
        html += `="${(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$entities$2f$dist$2f$esm$2f$escape$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["escapeAttribute"])(attr.value)}"`;
    }
    return html;
}
function serializeTextNode(node, options) {
    const { treeAdapter } = options;
    const content = treeAdapter.getTextNodeContent(node);
    const parent = treeAdapter.getParentNode(node);
    const parentTn = parent && treeAdapter.isElementNode(parent) && treeAdapter.getTagName(parent);
    return parentTn && treeAdapter.getNamespaceURI(parent) === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["NS"].HTML && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["hasUnescapedText"])(parentTn, options.scriptingEnabled) ? content : (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$entities$2f$dist$2f$esm$2f$escape$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["escapeText"])(content);
}
function serializeCommentNode(node, { treeAdapter }) {
    return `<!--${treeAdapter.getCommentNodeContent(node)}-->`;
}
function serializeDocumentTypeNode(node, { treeAdapter }) {
    return `<!DOCTYPE ${treeAdapter.getDocumentTypeNodeName(node)}>`;
}
}),
"[project]/coding/projects/LangBot/web/node_modules/parse5/dist/index.js [app-client] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "parse",
    ()=>parse,
    "parseFragment",
    ()=>parseFragment
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$parser$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/parser/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tree$2d$adapters$2f$default$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/tree-adapters/default.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$serializer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/serializer/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$error$2d$codes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/error-codes.js [app-client] (ecmascript)");
/** @internal */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$foreign$2d$content$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/foreign-content.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/html.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/token.js [app-client] (ecmascript)");
/** @internal */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$tokenizer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/tokenizer/index.js [app-client] (ecmascript)");
;
;
;
;
;
;
;
;
;
function parse(html, options) {
    return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$parser$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Parser"].parse(html, options);
}
function parseFragment(fragmentContext, html, options) {
    if (typeof fragmentContext === 'string') {
        options = html;
        html = fragmentContext;
        fragmentContext = null;
    }
    const parser = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$parser$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Parser"].getFragmentParser(fragmentContext, options);
    parser.tokenizer.write(html, true);
    return parser.getFragment();
}
}),
"[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/token.js [app-client] (ecmascript) <export * as Token>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Token",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$token$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/token.js [app-client] (ecmascript)");
}),
"[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/html.js [app-client] (ecmascript) <export * as html>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "html",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$parse5$2f$dist$2f$common$2f$html$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/parse5/dist/common/html.js [app-client] (ecmascript)");
}),
]);

//# sourceMappingURL=a2e30_parse5_dist_09a28ce7._.js.map