(function () {
  "use strict";

  // Prevent duplicate initialization
  if (document.getElementById("langbot-widget-root")) return;

  // Read config from script tag data attributes
  var scriptEl = document.currentScript;
  var scriptTitle = scriptEl ? scriptEl.getAttribute("data-title") : null;

  // ========== Configuration (injected by backend) ==========
  var CONFIG = {
    pipelineUuid: "__LANGBOT_PIPELINE_UUID__",
    baseUrl: "__LANGBOT_BASE_URL__",
    sessionType: "person",
    title: scriptTitle || "LangBot",
    logoUrl: "__LANGBOT_BASE_URL__" + "/api/v1/embed/logo",
    maxReconnectAttempts: 5,
    reconnectDelay: 3000,
    heartbeatInterval: 30000,
    turnstileSiteKey: "__LANGBOT_TURNSTILE_SITE_KEY__",
  };

  // ========== Styles ==========
  var STYLES =
    '\
    :host { all: initial; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; font-size: 14px; line-height: 1.5; color: #1a1a1a; }\
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }\
    .lb-bubble { position: fixed; bottom: 20px; right: 20px; width: 56px; height: 56px; border-radius: 50%; background: #2563eb; color: #fff; border: none; cursor: pointer; box-shadow: 0 4px 12px rgba(37,99,235,0.4); display: flex; align-items: center; justify-content: center; z-index: 2147483646; transition: transform 0.2s ease, box-shadow 0.2s ease; overflow: hidden; }\
    .lb-bubble:hover { transform: scale(1.08); box-shadow: 0 6px 20px rgba(37,99,235,0.5); }\
    .lb-bubble svg { width: 28px; height: 28px; fill: currentColor; }\
    .lb-bubble .lb-close-icon { display: none; }\
    .lb-bubble.lb-open .lb-chat-icon { display: none; }\
    .lb-bubble.lb-open .lb-close-icon { display: block; }\
    .lb-panel { position: fixed; bottom: 88px; right: 20px; width: 400px; height: 600px; max-height: calc(100vh - 108px); background: #fff; border-radius: 16px; box-shadow: 0 8px 40px rgba(0,0,0,0.15); display: flex; flex-direction: column; z-index: 2147483646; overflow: hidden; opacity: 0; transform: translateY(16px) scale(0.95); pointer-events: none; transition: opacity 0.25s ease, transform 0.25s ease; }\
    .lb-panel.lb-visible { opacity: 1; transform: translateY(0) scale(1); pointer-events: auto; }\
    .lb-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; background: #2563eb; color: #fff; flex-shrink: 0; }\
    .lb-header-left { display: flex; align-items: center; gap: 10px; }\
    .lb-header-logo { width: 28px; height: 28px; border-radius: 6px; object-fit: cover; }\
    .lb-header-title { font-size: 16px; font-weight: 600; }\
    .lb-status-dot { width: 8px; height: 8px; border-radius: 50%; background: #fbbf24; flex-shrink: 0; }\
    .lb-status-dot.lb-connected { background: #34d399; }\
    .lb-header-actions { display: flex; align-items: center; gap: 8px; }\
    .lb-header-btn { background: none; border: none; color: #fff; cursor: pointer; padding: 4px; border-radius: 6px; display: flex; align-items: center; justify-content: center; opacity: 0.8; transition: opacity 0.15s; }\
    .lb-header-btn:hover { opacity: 1; }\
    .lb-header-btn svg { width: 18px; height: 18px; fill: currentColor; }\
    .lb-messages { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 16px; scroll-behavior: smooth; }\
    .lb-messages::-webkit-scrollbar { width: 6px; }\
    .lb-messages::-webkit-scrollbar-track { background: transparent; }\
    .lb-messages::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 3px; }\
    .lb-msg { display: flex; gap: 10px; animation: lb-fade-in 0.2s ease; max-width: 100%; }\
    @keyframes lb-fade-in { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }\
    .lb-msg-user { flex-direction: row-reverse; }\
    .lb-msg-assistant { flex-direction: row; }\
    .lb-avatar { width: 32px; height: 32px; border-radius: 50%; flex-shrink: 0; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 600; overflow: hidden; }\
    .lb-avatar svg { width: 18px; height: 18px; fill: #fff; }\
    .lb-avatar img { width: 100%; height: 100%; object-fit: cover; }\
    .lb-avatar-user { background: #6366f1; color: #fff; }\
    .lb-avatar-bot { background: #5b9bd5; color: #fff; }\
    .lb-msg-body { display: flex; flex-direction: column; max-width: calc(100% - 42px); min-width: 0; }\
    .lb-msg-user .lb-msg-body { align-items: flex-end; }\
    .lb-msg-assistant .lb-msg-body { align-items: flex-start; }\
    .lb-msg-bubble { padding: 10px 14px; border-radius: 12px; word-break: break-word; white-space: pre-wrap; font-size: 14px; line-height: 1.6; max-width: 100%; }\
    .lb-msg-user .lb-msg-bubble { background: #2563eb; color: #fff; border-bottom-right-radius: 4px; }\
    .lb-msg-assistant .lb-msg-bubble { background: #f3f4f6; color: #1a1a1a; border-bottom-left-radius: 4px; }\
    .lb-msg-bubble code { font-family: "SF Mono", Monaco, Consolas, monospace; font-size: 0.9em; background: rgba(0,0,0,0.06); padding: 1px 4px; border-radius: 3px; }\
    .lb-msg-user .lb-msg-bubble code { background: rgba(255,255,255,0.2); }\
    .lb-msg-bubble pre { background: #1e293b; color: #e2e8f0; padding: 12px; border-radius: 8px; overflow-x: auto; margin: 8px 0; font-size: 13px; }\
    .lb-msg-bubble pre code { background: none; padding: 0; color: inherit; }\
    .lb-msg-bubble a { color: #2563eb; text-decoration: underline; }\
    .lb-msg-user .lb-msg-bubble a { color: #bfdbfe; }\
    .lb-msg-bubble h3 { font-size: 15px; font-weight: 600; margin: 8px 0 4px; }\
    .lb-msg-bubble h4 { font-size: 14px; font-weight: 600; margin: 6px 0 3px; }\
    .lb-msg-bubble blockquote { border-left: 3px solid #d1d5db; padding-left: 10px; margin: 6px 0; color: #6b7280; }\
    .lb-msg-bubble ul, .lb-msg-bubble ol { padding-left: 20px; margin: 4px 0; }\
    .lb-msg-bubble li { margin: 2px 0; }\
    .lb-msg-bubble table { border-collapse: collapse; margin: 8px 0; font-size: 13px; width: 100%; }\
    .lb-msg-bubble th, .lb-msg-bubble td { border: 1px solid #d1d5db; padding: 4px 8px; text-align: left; }\
    .lb-msg-bubble th { background: #f3f4f6; font-weight: 600; }\
    .lb-msg-bubble hr { border: none; border-top: 1px solid #d1d5db; margin: 8px 0; }\
    .lb-msg-bubble del { text-decoration: line-through; opacity: 0.7; }\
    .lb-msg-bubble img { max-width: 100%; border-radius: 8px; margin: 4px 0; cursor: pointer; }\
    .lb-msg-actions { display: flex; align-items: center; gap: 4px; margin-top: 6px; padding-top: 6px; border-top: 1px solid rgba(0,0,0,0.06); }\
    .lb-msg-actions-hidden { display: none; }\
    .lb-act-btn { background: none; border: 1px solid #e5e7eb; color: #9ca3af; cursor: pointer; padding: 3px 6px; border-radius: 6px; display: flex; align-items: center; gap: 3px; font-size: 11px; transition: all 0.15s; }\
    .lb-act-btn:hover { background: #f3f4f6; color: #6b7280; border-color: #d1d5db; }\
    .lb-act-btn.lb-active { color: #2563eb; border-color: #93c5fd; background: #eff6ff; }\
    .lb-act-btn svg { width: 14px; height: 14px; fill: currentColor; }\
    .lb-img-upload-btn { background: none; border: none; color: #9ca3af; cursor: pointer; padding: 6px; border-radius: 8px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; transition: color 0.15s; }\
    .lb-img-upload-btn:hover { color: #6b7280; }\
    .lb-img-upload-btn svg { width: 20px; height: 20px; fill: currentColor; }\
    .lb-img-preview { display: flex; align-items: center; gap: 8px; padding: 8px 16px; border-top: 1px solid #e5e7eb; background: #fafafa; flex-shrink: 0; }\
    .lb-img-preview img { width: 48px; height: 48px; object-fit: cover; border-radius: 6px; }\
    .lb-img-preview-remove { background: none; border: none; color: #9ca3af; cursor: pointer; font-size: 18px; padding: 0 4px; }\
    .lb-img-preview-remove:hover { color: #ef4444; }\
    .lb-msg-meta { display: flex; align-items: center; gap: 8px; margin-top: 4px; padding: 0 2px; }\
    .lb-msg-time { font-size: 11px; color: #9ca3af; }\
    .lb-footer { text-align: right; padding: 2px 12px 0; font-size: 9px; color: #d1d5db; font-style: italic; flex-shrink: 0; }\
    .lb-footer a { color: #d1d5db; text-decoration: none; }\
    .lb-footer a:hover { color: #9ca3af; }\
    .lb-typing { display: inline-flex; gap: 4px; padding: 10px 14px; background: #f3f4f6; border-radius: 12px; border-bottom-left-radius: 4px; margin-left: 42px; }\
    .lb-typing span { width: 6px; height: 6px; background: #9ca3af; border-radius: 50%; animation: lb-bounce 1.4s infinite both; }\
    .lb-typing span:nth-child(2) { animation-delay: 0.16s; }\
    .lb-typing span:nth-child(3) { animation-delay: 0.32s; }\
    @keyframes lb-bounce { 0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; } 40% { transform: scale(1); opacity: 1; } }\
    .lb-welcome { text-align: center; color: #9ca3af; padding: 40px 20px; font-size: 14px; }\
    .lb-welcome-logo { width: 48px; height: 48px; border-radius: 12px; margin: 0 auto 12px; }\
    .lb-input-area { display: flex; align-items: flex-end; gap: 8px; padding: 12px 16px; border-top: 1px solid #e5e7eb; background: #fff; flex-shrink: 0; }\
    .lb-input { flex: 1; border: 1px solid #d1d5db; border-radius: 10px; padding: 10px 14px; font-size: 14px; font-family: inherit; line-height: 1.4; resize: none; outline: none; max-height: 120px; min-height: 40px; transition: border-color 0.15s; overflow-y: auto; }\
    .lb-input:focus { border-color: #2563eb; }\
    .lb-input::placeholder { color: #9ca3af; }\
    .lb-send-btn { width: 40px; height: 40px; border-radius: 10px; background: #2563eb; color: #fff; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; transition: background 0.15s, opacity 0.15s; }\
    .lb-send-btn:hover { background: #1d4ed8; }\
    .lb-send-btn:disabled { opacity: 0.4; cursor: not-allowed; }\
    .lb-send-btn svg { width: 20px; height: 20px; fill: currentColor; }\
    .lb-error { text-align: center; color: #ef4444; padding: 8px; font-size: 12px; background: #fef2f2; border-radius: 8px; margin: 4px 16px; }\
    @media (max-width: 480px) {\
      .lb-panel { bottom: 0; right: 0; width: 100vw; height: 100vh; max-height: 100vh; border-radius: 0; }\
      .lb-bubble { bottom: 16px; right: 16px; }\
    }\
  ';

  // ========== SVG Icons ==========
  var ICON_CLOSE =
    '<svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>';
  var ICON_SEND =
    '<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>';
  var ICON_RESET =
    '<svg viewBox="0 0 24 24"><path d="M17.65 6.35A7.96 7.96 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>';
  var ICON_USER =
    '<svg viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>';
  var ICON_THUMB_UP =
    '<svg viewBox="0 0 24 24"><path d="M2 20h2c.55 0 1-.45 1-1v-9c0-.55-.45-1-1-1H2v11zm19.83-7.12c.11-.25.17-.52.17-.8V11c0-1.1-.9-2-2-2h-5.5l.92-4.65c.05-.22.02-.46-.08-.66-.23-.45-.52-.86-.88-1.22L14 2 7.59 8.41C7.21 8.79 7 9.3 7 9.83v7.84C7 18.95 8.05 20 9.34 20h8.11c.7 0 1.36-.37 1.72-.97l2.66-6.15z"/></svg>';
  var ICON_THUMB_DOWN =
    '<svg viewBox="0 0 24 24"><path d="M22 4h-2c-.55 0-1 .45-1 1v9c0 .55.45 1 1 1h2V4zM2.17 11.12c-.11.25-.17.52-.17.8V13c0 1.1.9 2 2 2h5.5l-.92 4.65c-.05.22-.02.46.08.66.23.45.52.86.88 1.22L10 22l6.41-6.41c.38-.38.59-.89.59-1.42V6.34C17 5.05 15.95 4 14.66 4h-8.1c-.71 0-1.36.37-1.72.97l-2.67 6.15z"/></svg>';
  var ICON_COPY =
    '<svg viewBox="0 0 24 24"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>';
  var ICON_CHECK =
    '<svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>';
  var ICON_IMAGE =
    '<svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zM6 20V4h7v5h5v11H6z"/><path d="M8 17l2.5-3.5L13 17l2-2.5L18 17H8z"/></svg>';

  // ========== State ==========
  var state = {
    isOpen: false,
    isConnected: false,
    ws: null,
    connectionId: null,
    reconnectAttempts: 0,
    heartbeatTimer: null,
    messages: [],
    nextLocalId: 1,
    isStreaming: false,
    streamingMsgId: null,
    historyLoaded: false,
    pendingImage: null,
    feedbackState: {},
  };

  // ========== DOM References ==========
  var els = {};

  // ========== Utility Functions ==========
  function esc(str) {
    var div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function formatTime(ts) {
    try {
      var d = new Date(ts);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch (e) {
      return "";
    }
  }

  function renderMarkdown(text) {
    if (!text) return "";
    // Preserve code blocks first
    var codeBlocks = [];
    text = text.replace(/```(\w*)\n?([\s\S]*?)```/g, function (m, lang, code) {
      codeBlocks.push("<pre><code>" + esc(code.trim()) + "</code></pre>");
      return "\x00CB" + (codeBlocks.length - 1) + "\x00";
    });
    var html = esc(text);
    // Restore code blocks
    html = html.replace(/\x00CB(\d+)\x00/g, function (m, i) {
      return codeBlocks[parseInt(i)];
    });
    // Inline code
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    // Headings
    html = html.replace(/^### (.+)$/gm, "<h4>$1</h4>");
    html = html.replace(/^## (.+)$/gm, "<h4>$1</h4>");
    html = html.replace(/^# (.+)$/gm, "<h3>$1</h3>");
    // Horizontal rules
    html = html.replace(/^---$/gm, "<hr>");
    // Blockquotes
    html = html.replace(/^&gt; (.+)$/gm, "<blockquote>$1</blockquote>");
    // Tables
    html = html.replace(/((?:\|.+\|\n?)+)/g, function (table) {
      var rows = table.trim().split("\n");
      if (rows.length < 2) return table;
      var out = "<table>";
      for (var r = 0; r < rows.length; r++) {
        if (r === 1 && /^\|[\s\-:|]+\|$/.test(rows[r])) continue;
        var cells = rows[r].split("|").filter(function (c, i, a) {
          return i > 0 && i < a.length - 1;
        });
        var tag = r === 0 ? "th" : "td";
        out +=
          "<tr>" +
          cells
            .map(function (c) {
              return "<" + tag + ">" + c.trim() + "</" + tag + ">";
            })
            .join("") +
          "</tr>";
      }
      return out + "</table>";
    });
    // Strikethrough
    html = html.replace(/~~([^~]+)~~/g, "<del>$1</del>");
    // Bold
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    // Italic
    html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    // Links
    html = html.replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      function (match, p1, p2) {
        if (/^https?:\/\//i.test(p2)) {
          return '<a href="' + p2 + '" target="_blank" rel="noopener noreferrer">' + p1 + '</a>';
        }
        return p1;
      }
    );
    // Unordered lists
    html = html.replace(/((?:^[\-\*] .+(?:<br>)?)+)/gm, function (block) {
      var items = block.split(/<br>|\\n/).filter(function (l) {
        return /^[\-\*] /.test(l.trim());
      });
      return (
        "<ul>" +
        items
          .map(function (l) {
            return "<li>" + l.replace(/^[\-\*] /, "") + "</li>";
          })
          .join("") +
        "</ul>"
      );
    });
    // Ordered lists
    html = html.replace(/((?:^\d+\. .+(?:<br>)?)+)/gm, function (block) {
      var items = block.split(/<br>|\\n/).filter(function (l) {
        return /^\d+\. /.test(l.trim());
      });
      return (
        "<ol>" +
        items
          .map(function (l) {
            return "<li>" + l.replace(/^\d+\. /, "") + "</li>";
          })
          .join("") +
        "</ol>"
      );
    });
    // Line breaks (but not inside block elements)
    html = html.replace(/\n/g, "<br>");
    // Clean up excessive <br> around block elements
    html = html.replace(
      /<br>\s*(<(?:h[34]|pre|table|ul|ol|blockquote|hr))/g,
      "$1",
    );
    html = html.replace(
      /(<\/(?:h[34]|pre|table|ul|ol|blockquote)>)\s*<br>/g,
      "$1",
    );
    return html;
  }

  function scrollToBottom() {
    if (els.messages) {
      requestAnimationFrame(function () {
        els.messages.scrollTop = els.messages.scrollHeight;
      });
    }
  }

  // ========== WebSocket Client ==========
  function wsConnect() {
    if (
      state.ws &&
      (state.ws.readyState === WebSocket.OPEN ||
        state.ws.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    var protocol = CONFIG.baseUrl.indexOf("https") === 0 ? "wss:" : "ws:";
    var host = CONFIG.baseUrl.replace(/^https?:\/\//, "");
    var url =
      protocol +
      "//" +
      host +
      "/api/v1/pipelines/" +
      CONFIG.pipelineUuid +
      "/ws/connect?session_type=" +
      CONFIG.sessionType;

    try {
      state.ws = new WebSocket(url);
    } catch (e) {
      showError("Failed to connect");
      return;
    }

    state.ws.onopen = function () {
      state.reconnectAttempts = 0;
      startHeartbeat();
    };

    state.ws.onmessage = function (event) {
      try {
        var data = JSON.parse(event.data);
        handleWsMessage(data);
      } catch (e) {
        // ignore parse errors
      }
    };

    state.ws.onclose = function () {
      state.isConnected = false;
      updateStatusDot();
      updateSendBtn();
      stopHeartbeat();

      if (state.reconnectAttempts < CONFIG.maxReconnectAttempts) {
        state.reconnectAttempts++;
        setTimeout(wsConnect, CONFIG.reconnectDelay * state.reconnectAttempts);
      }
    };

    state.ws.onerror = function () {
      state.isConnected = false;
      updateStatusDot();
      updateSendBtn();
    };
  }

  function handleWsMessage(data) {
    switch (data.type) {
      case "connected":
        state.isConnected = true;
        state.connectionId = data.connection_id;
        updateStatusDot();
        updateSendBtn();
        break;

      case "response":
        if (data.session_type && data.session_type !== CONFIG.sessionType)
          break;
        if (data.data) handleAssistantMessage(data.data);
        break;

      case "user_message":
        if (data.session_type && data.session_type !== CONFIG.sessionType)
          break;
        // Only show messages from OTHER connections (own messages are added locally)
        if (data.data && data.data.connection_id !== state.connectionId) {
          addMessage(data.data);
        }
        break;

      case "pong":
        break;

      case "error":
        showError(data.message || "Unknown error");
        break;
    }
  }

  function handleAssistantMessage(msg) {
    // Streaming: update existing message with same id
    var existingIdx = -1;
    for (var i = state.messages.length - 1; i >= 0; i--) {
      if (
        state.messages[i].id === msg.id &&
        state.messages[i].role === "assistant"
      ) {
        existingIdx = i;
        break;
      }
    }

    // Deduplicate: if any assistant message since last user message has the same content, skip
    if (existingIdx < 0) {
      var content = (msg.content || extractText(msg))
        .replace(/\s+/g, " ")
        .trim();
      if (content) {
        for (var j = state.messages.length - 1; j >= 0; j--) {
          var prev = state.messages[j];
          if (prev.role === "user") break;
          if (prev.role === "assistant") {
            var prevContent = (prev.content || extractText(prev))
              .replace(/\s+/g, " ")
              .trim();
            if (
              prevContent === content ||
              prevContent.indexOf(content) >= 0 ||
              content.indexOf(prevContent) >= 0
            )
              return;
          }
        }
      }
    }

    if (existingIdx >= 0) {
      state.messages[existingIdx] = msg;
      updateMessageEl(existingIdx, msg);
    } else {
      addMessage(msg);
    }

    state.isStreaming = !msg.is_final;
    state.streamingMsgId = msg.is_final ? null : msg.id;

    if (msg.is_final) {
      removeTypingIndicator();
    }

    scrollToBottom();
  }

  function sendMessage(text, imageBase64) {
    if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return;
    if (!text.trim() && !imageBase64) return;

    var chain = [];
    if (text.trim()) chain.push({ type: "Plain", text: text.trim() });
    if (imageBase64) chain.push({ type: "Image", base64: imageBase64 });

    var localMsg = {
      id: "local_" + state.nextLocalId++,
      role: "user",
      content: text.trim(),
      message_chain: chain,
      timestamp: new Date().toISOString(),
      is_final: true,
    };
    addMessage(localMsg);

    state.ws.send(
      JSON.stringify({ type: "message", message: chain, stream: true }),
    );
  }

  function startHeartbeat() {
    stopHeartbeat();
    state.heartbeatTimer = setInterval(function () {
      if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({ type: "ping" }));
      }
    }, CONFIG.heartbeatInterval);
  }

  function stopHeartbeat() {
    if (state.heartbeatTimer) {
      clearInterval(state.heartbeatTimer);
      state.heartbeatTimer = null;
    }
  }

  function wsDisconnect() {
    stopHeartbeat();
    state.reconnectAttempts = CONFIG.maxReconnectAttempts;
    if (state.ws) {
      if (state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({ type: "disconnect" }));
      }
      state.ws.close();
      state.ws = null;
    }
    state.isConnected = false;
    state.connectionId = null;
  }

  // ========== Message History ==========
  function loadHistory() {
    if (state.historyLoaded) return;
    state.historyLoaded = true;

    var url =
      CONFIG.baseUrl +
      "/api/v1/embed/" +
      CONFIG.pipelineUuid +
      "/messages/" +
      CONFIG.sessionType;
    var headers = {};
    if (state.sessionToken) headers["Authorization"] = "Bearer " + state.sessionToken;
    fetch(url, { headers: headers })
      .then(function (res) {
        return res.json();
      })
      .then(function (json) {
        if (json.code === 0 && json.data && json.data.messages) {
          var msgs = json.data.messages;
          for (var i = 0; i < msgs.length; i++) {
            addMessage(msgs[i], true);
          }
          scrollToBottom();
        }
      })
      .catch(function () {
        // silently ignore history load errors
      });
  }

  function resetSession() {
    var url =
      CONFIG.baseUrl +
      "/api/v1/embed/" +
      CONFIG.pipelineUuid +
      "/reset/" +
      CONFIG.sessionType;
    var headers = {};
    if (state.sessionToken) headers["Authorization"] = "Bearer " + state.sessionToken;
    fetch(url, { method: "POST", headers: headers })
      .then(function () {
        state.messages = [];
        state.isStreaming = false;
        state.streamingMsgId = null;
        state.historyLoaded = true;
        renderMessages();
      })
      .catch(function () {
        // ignore
      });
  }

  // ========== UI Rendering ==========
  function addMessage(msg, silent) {
    state.messages.push(msg);
    var el = createMessageEl(msg);
    if (els.welcome) {
      els.welcome.style.display = "none";
    }
    els.messages.appendChild(el);
    if (!silent) scrollToBottom();
  }

  function createMessageEl(msg) {
    var isUser = msg.role === "user";
    var div = document.createElement("div");
    div.className = "lb-msg " + (isUser ? "lb-msg-user" : "lb-msg-assistant");
    div.dataset.msgId = msg.id;

    // Avatar
    var avatar = document.createElement("div");
    avatar.className =
      "lb-avatar " + (isUser ? "lb-avatar-user" : "lb-avatar-bot");
    if (isUser) {
      avatar.innerHTML = ICON_USER;
    } else {
      var logoImg = document.createElement("img");
      logoImg.src = CONFIG.logoUrl;
      logoImg.alt = "Bot";
      avatar.appendChild(logoImg);
    }

    // Message body (bubble + meta)
    var body = document.createElement("div");
    body.className = "lb-msg-body";

    var bubble = document.createElement("div");
    bubble.className = "lb-msg-bubble";
    var textContent = msg.content || extractText(msg);
    bubble.innerHTML = isUser ? esc(textContent) : renderMarkdown(textContent);

    // Render images from message chain
    var images = extractImages(msg);
    for (var ii = 0; ii < images.length; ii++) {
      var img = document.createElement("img");
      img.src = images[ii];
      img.alt = "Image";
      bubble.appendChild(img);
    }

    // Meta row: time
    var meta = document.createElement("div");
    meta.className = "lb-msg-meta";

    var time = document.createElement("span");
    time.className = "lb-msg-time";
    time.textContent = formatTime(msg.timestamp);
    meta.appendChild(time);

    body.appendChild(bubble);
    body.appendChild(meta);

    // Action buttons for assistant messages (copy, like, dislike) — inside bubble, hidden during streaming
    if (!isUser) {
      var actions = document.createElement("div");
      actions.className =
        "lb-msg-actions" +
        (msg.is_final === false ? " lb-msg-actions-hidden" : "");

      // Copy button
      var copyBtn = document.createElement("button");
      copyBtn.className = "lb-act-btn";
      copyBtn.innerHTML = ICON_COPY;
      copyBtn.addEventListener(
        "click",
        (function (t) {
          return function () {
            var currentText = bubble.textContent || t;
            navigator.clipboard.writeText(currentText).then(function () {
              copyBtn.innerHTML = ICON_CHECK;
              setTimeout(function () {
                copyBtn.innerHTML = ICON_COPY;
              }, 1500);
            });
          };
        })(textContent),
      );
      actions.appendChild(copyBtn);

      // Like & Dislike buttons
      var likeBtn = document.createElement("button");
      var dislikeBtn = document.createElement("button");

      likeBtn.className =
        "lb-act-btn" + (state.feedbackState[msg.id] === 1 ? " lb-active" : "");
      likeBtn.innerHTML = ICON_THUMB_UP;
      dislikeBtn.className =
        "lb-act-btn" + (state.feedbackState[msg.id] === 2 ? " lb-active" : "");
      dislikeBtn.innerHTML = ICON_THUMB_DOWN;

      (function (id, lBtn, dBtn) {
        lBtn.addEventListener("click", function () {
          submitFeedback(id, 1);
          lBtn.classList.toggle("lb-active", state.feedbackState[id] === 1);
          dBtn.classList.remove("lb-active");
        });
        dBtn.addEventListener("click", function () {
          submitFeedback(id, 2);
          dBtn.classList.toggle("lb-active", state.feedbackState[id] === 2);
          lBtn.classList.remove("lb-active");
        });
      })(msg.id, likeBtn, dislikeBtn);

      actions.appendChild(likeBtn);
      actions.appendChild(dislikeBtn);
      bubble.appendChild(actions);
    }

    div.appendChild(avatar);
    div.appendChild(body);
    return div;
  }

  function extractText(msg) {
    if (msg.content) return msg.content;
    if (msg.message_chain) {
      var texts = [];
      for (var i = 0; i < msg.message_chain.length; i++) {
        if (msg.message_chain[i].text) texts.push(msg.message_chain[i].text);
      }
      return texts.join("");
    }
    return "";
  }

  function extractImages(msg) {
    var images = [];
    if (msg.message_chain) {
      for (var i = 0; i < msg.message_chain.length; i++) {
        var c = msg.message_chain[i];
        if (c.type === "Image" && (c.base64 || c.url)) {
          var imgUrl = c.base64 || c.url;
          if (/^(https?:\/\/|data:)/i.test(imgUrl)) {
            images.push(imgUrl);
          }
        }
      }
    }
    return images;
  }

  function submitFeedback(msgId, feedbackType) {
    var prev = state.feedbackState[msgId];
    var actualType = prev === feedbackType ? 3 : feedbackType; // toggle = cancel
    state.feedbackState[msgId] = actualType === 3 ? 0 : actualType;

    var headers = { "Content-Type": "application/json" };
    if (state.sessionToken) headers["Authorization"] = "Bearer " + state.sessionToken;

    fetch(
      CONFIG.baseUrl + "/api/v1/embed/" + CONFIG.pipelineUuid + "/feedback",
      {
        method: "POST",
        headers: headers,
        body: JSON.stringify({ message_id: msgId, feedback_type: actualType }),
      },
    ).catch(function () {});
  }

  function updateMessageEl(idx, msg) {
    var allMsgs = els.messages.querySelectorAll(".lb-msg");
    if (allMsgs[idx]) {
      var bubble = allMsgs[idx].querySelector(".lb-msg-bubble");
      if (bubble) {
        // Preserve action buttons if present
        var actionsEl = bubble.querySelector(".lb-msg-actions");
        bubble.innerHTML = renderMarkdown(msg.content || extractText(msg));
        // Re-append or show action buttons when streaming finishes
        if (actionsEl) {
          if (msg.is_final) actionsEl.classList.remove("lb-msg-actions-hidden");
          bubble.appendChild(actionsEl);
        }
      }
    }
  }

  function renderMessages() {
    // Clear all messages from DOM
    while (els.messages.firstChild) {
      els.messages.removeChild(els.messages.firstChild);
    }

    // Re-add welcome if no messages
    if (state.messages.length === 0) {
      els.messages.appendChild(createWelcomeEl());
      return;
    }

    for (var i = 0; i < state.messages.length; i++) {
      els.messages.appendChild(createMessageEl(state.messages[i]));
    }
    scrollToBottom();
  }

  function createWelcomeEl() {
    var div = document.createElement("div");
    div.className = "lb-welcome";
    els.welcome = div;

    var logo = document.createElement("img");
    logo.className = "lb-welcome-logo";
    logo.src = CONFIG.logoUrl;
    logo.alt = "LangBot";

    var text = document.createElement("div");
    text.textContent = "Send a message to start the conversation";

    div.appendChild(logo);
    div.appendChild(text);
    return div;
  }

  function showTypingIndicator() {
    if (els.messages.querySelector(".lb-typing")) return;
    var div = document.createElement("div");
    div.className = "lb-typing";
    div.innerHTML = "<span></span><span></span><span></span>";
    els.messages.appendChild(div);
    scrollToBottom();
  }

  function removeTypingIndicator() {
    var el = els.messages.querySelector(".lb-typing");
    if (el) el.remove();
  }

  function showError(msg) {
    var div = document.createElement("div");
    div.className = "lb-error";
    div.textContent = msg;
    els.messages.appendChild(div);
    setTimeout(function () {
      if (div.parentNode) div.remove();
    }, 5000);
    scrollToBottom();
  }

  function updateStatusDot() {
    if (els.statusDot) {
      if (state.isConnected) {
        els.statusDot.classList.add("lb-connected");
      } else {
        els.statusDot.classList.remove("lb-connected");
      }
    }
  }

  function updateSendBtn() {
    if (els.sendBtn) {
      els.sendBtn.disabled = !state.isConnected;
    }
  }

  function togglePanel() {
    state.isOpen = !state.isOpen;

    if (state.isOpen) {
      els.panel.classList.add("lb-visible");
      els.bubble.classList.add("lb-open");
      ensureTurnstileVerified(function() {
        loadHistory();
        wsConnect();
      });
      setTimeout(function () {
        if (els.input) els.input.focus();
      }, 300);
    } else {
      els.panel.classList.remove("lb-visible");
      els.bubble.classList.remove("lb-open");
    }
  }

  function ensureTurnstileVerified(callback) {
    if (state.sessionToken || !CONFIG.turnstileSiteKey || CONFIG.turnstileSiteKey.indexOf("__LANGBOT") === 0) {
      return callback();
    }
    if (state.turnstileQueue) {
      state.turnstileQueue.push(callback);
      return;
    }
    state.turnstileQueue = [callback];

    var flushQueue = function(success) {
      var q = state.turnstileQueue;
      state.turnstileQueue = null;
      if (success && q) {
        for (var i=0; i<q.length; i++) q[i]();
      }
    };

    var doRender = function() {
      var container = document.createElement("div");
      document.body.appendChild(container);
      turnstile.render(container, {
        sitekey: CONFIG.turnstileSiteKey,
        size: "invisible",
        callback: function(token) {
          fetch(CONFIG.baseUrl + "/api/v1/embed/" + CONFIG.pipelineUuid + "/turnstile/verify", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token: token })
          }).then(function(res) { return res.json(); })
            .then(function(data) {
              if (data && data.data && data.data.token) {
                state.sessionToken = data.data.token;
                flushQueue(true);
              } else {
                showError("Bot verification failed");
                flushQueue(false);
              }
            }).catch(function() {
              showError("Bot verification network error");
              flushQueue(false);
            });
        },
        "error-callback": function() {
          showError("Bot verification error");
          flushQueue(false);
        }
      });
    };

    if (window.turnstile) {
      doRender();
    } else {
      window.onloadTurnstileCallback = doRender;
      var script = document.createElement("script");
      script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit&onload=onloadTurnstileCallback";
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }
  }

  function handleSend() {
    var text = els.input.value;
    var img = state.pendingImage;
    if ((!text.trim() && !img) || !state.isConnected) return;

    sendMessage(text, img);
    els.input.value = "";
    els.input.style.height = "auto";
    clearPendingAttachment();
    els.input.focus();
  }

  function handleInputKeydown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function autoResizeInput() {
    els.input.style.height = "auto";
    els.input.style.height = Math.min(els.input.scrollHeight, 120) + "px";
  }

  function handleImageSelect(e) {
    var file = e.target.files && e.target.files[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      showError("Image must be under 5MB");
      return;
    }
    if (!/^image\//.test(file.type)) {
      showError("Only image files are supported");
      return;
    }
    var reader = new FileReader();
    reader.onload = function (ev) {
      showImagePreview(ev.target.result);
      state.pendingImage = ev.target.result;
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  }

  function showImagePreview(src) {
    removePreviewDom();
    var preview = document.createElement("div");
    preview.className = "lb-img-preview";
    preview.id = "lb-img-preview";

    var img = document.createElement("img");
    img.src = src;

    var removeBtn = document.createElement("button");
    removeBtn.className = "lb-img-preview-remove";
    removeBtn.textContent = "\u00d7";
    removeBtn.addEventListener("click", clearPendingAttachment);

    preview.appendChild(img);
    preview.appendChild(removeBtn);

    // Insert before footer
    var footer = els.panel.querySelector(".lb-footer");
    if (footer) {
      footer.parentNode.insertBefore(preview, footer);
    }
  }

  function removePreviewDom() {
    var existing = els.panel
      ? els.panel.querySelector("#lb-img-preview")
      : null;
    if (existing) existing.remove();
  }

  function clearPendingAttachment() {
    state.pendingImage = null;
    state.pendingFile = null;
    removePreviewDom();
  }

  // ========== Build DOM ==========
  function buildWidget() {
    // Root container
    var root = document.createElement("div");
    root.id = "langbot-widget-root";
    document.body.appendChild(root);

    var shadow = root.attachShadow({ mode: "open" });

    // Styles
    var style = document.createElement("style");
    style.textContent = STYLES;
    shadow.appendChild(style);

    // Chat bubble button
    var bubble = document.createElement("button");
    bubble.className = "lb-bubble";
    bubble.setAttribute("aria-label", "Open chat");

    var chatIcon = document.createElement("span");
    chatIcon.className = "lb-chat-icon";
    var bubbleLogo = document.createElement("img");
    bubbleLogo.src = CONFIG.logoUrl;
    bubbleLogo.alt = CONFIG.title;
    bubbleLogo.style.cssText = "width:100%;height:100%;object-fit:cover;";
    chatIcon.appendChild(bubbleLogo);

    var closeIcon = document.createElement("span");
    closeIcon.className = "lb-close-icon";
    closeIcon.innerHTML = ICON_CLOSE;

    bubble.appendChild(chatIcon);
    bubble.appendChild(closeIcon);
    bubble.addEventListener("click", togglePanel);
    els.bubble = bubble;
    shadow.appendChild(bubble);

    // Chat panel
    var panel = document.createElement("div");
    panel.className = "lb-panel";
    els.panel = panel;

    // Header
    var header = document.createElement("div");
    header.className = "lb-header";

    var headerLeft = document.createElement("div");
    headerLeft.className = "lb-header-left";

    var headerLogo = document.createElement("img");
    headerLogo.className = "lb-header-logo";
    headerLogo.src = CONFIG.logoUrl;
    headerLogo.alt = CONFIG.title;

    var title = document.createElement("span");
    title.className = "lb-header-title";
    title.textContent = CONFIG.title;

    var statusDot = document.createElement("span");
    statusDot.className = "lb-status-dot";
    els.statusDot = statusDot;

    headerLeft.appendChild(headerLogo);
    headerLeft.appendChild(title);
    headerLeft.appendChild(statusDot);

    var headerActions = document.createElement("div");
    headerActions.className = "lb-header-actions";

    var resetBtn = document.createElement("button");
    resetBtn.className = "lb-header-btn";
    resetBtn.setAttribute("aria-label", "Reset conversation");
    resetBtn.innerHTML = ICON_RESET;
    resetBtn.addEventListener("click", resetSession);

    var minimizeBtn = document.createElement("button");
    minimizeBtn.className = "lb-header-btn";
    minimizeBtn.setAttribute("aria-label", "Minimize");
    minimizeBtn.innerHTML = ICON_CLOSE;
    minimizeBtn.addEventListener("click", togglePanel);

    headerActions.appendChild(resetBtn);
    headerActions.appendChild(minimizeBtn);

    header.appendChild(headerLeft);
    header.appendChild(headerActions);
    panel.appendChild(header);

    // Messages area
    var messages = document.createElement("div");
    messages.className = "lb-messages";
    els.messages = messages;
    messages.appendChild(createWelcomeEl());
    panel.appendChild(messages);

    // Input area
    var inputArea = document.createElement("div");
    inputArea.className = "lb-input-area";

    // Hidden file input
    var fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.accept = "image/*";
    fileInput.style.cssText =
      "position:absolute;width:0;height:0;overflow:hidden;opacity:0;";
    fileInput.addEventListener("change", handleImageSelect);

    // Image upload button
    var imgBtn = document.createElement("button");
    imgBtn.className = "lb-img-upload-btn";
    imgBtn.setAttribute("aria-label", "Upload file");
    imgBtn.innerHTML = ICON_IMAGE;
    imgBtn.addEventListener("click", function () {
      fileInput.click();
    });

    var input = document.createElement("textarea");
    input.className = "lb-input";
    input.placeholder = "Type a message...";
    input.rows = 1;
    input.addEventListener("keydown", handleInputKeydown);
    input.addEventListener("input", autoResizeInput);
    els.input = input;

    var sendBtn = document.createElement("button");
    sendBtn.className = "lb-send-btn";
    sendBtn.disabled = true;
    sendBtn.setAttribute("aria-label", "Send");
    sendBtn.innerHTML = ICON_SEND;
    sendBtn.addEventListener("click", handleSend);
    els.sendBtn = sendBtn;

    inputArea.appendChild(fileInput);
    inputArea.appendChild(imgBtn);
    inputArea.appendChild(input);
    inputArea.appendChild(sendBtn);

    // Footer: Powered by LangBot (above input area)
    var footer = document.createElement("div");
    footer.className = "lb-footer";
    footer.innerHTML =
      'Powered by <a href="https://github.com/langbot-app/LangBot" target="_blank" rel="noopener noreferrer">LangBot</a>';
    panel.appendChild(footer);

    panel.appendChild(inputArea);

    shadow.appendChild(panel);
  }

  // ========== Initialize ==========
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", buildWidget);
  } else {
    buildWidget();
  }
})();
