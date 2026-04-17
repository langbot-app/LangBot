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
    .lb-msg-meta { display: flex; align-items: center; gap: 8px; margin-top: 4px; padding: 0 2px; }\
    .lb-msg-time { font-size: 11px; color: #9ca3af; }\
    .lb-footer { text-align: right; padding: 2px 12px 0; font-size: 9px; color: #d1d5db; font-style: italic; flex-shrink: 0; }\
    .lb-footer a { color: #d1d5db; text-decoration: none; }\
    .lb-footer a:hover { color: #9ca3af; }\
    .lb-input-area { display: inline-flex; gap: 4px; padding: 10px 14px; background: #f3f4f6; border-radius: 12px; border-bottom-left-radius: 4px; margin-left: 42px; }\
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
    var html = esc(text);
    // Code blocks (``` ... ```)
    html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, function (m, lang, code) {
      return "<pre><code>" + code.trim() + "</code></pre>";
    });
    // Inline code
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    // Bold
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    // Italic
    html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    // Links
    html = html.replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
    );
    // Line breaks
    html = html.replace(/\n/g, "<br>");
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

    // Deduplicate: if we already have a final assistant message with the same content, skip
    if (existingIdx < 0 && msg.is_final) {
      var content = msg.content || extractText(msg);
      for (var j = state.messages.length - 1; j >= 0; j--) {
        var prev = state.messages[j];
        if (prev.role === "assistant" && prev.is_final) {
          var prevContent = prev.content || extractText(prev);
          if (prevContent === content) return;
          break;
        }
        if (prev.role === "user") break;
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
    } else {
      showTypingIndicator();
    }

    scrollToBottom();
  }

  function sendMessage(text) {
    if (!state.ws || state.ws.readyState !== WebSocket.OPEN || !text.trim())
      return;

    // Add user message to local chat immediately
    var localMsg = {
      id: "local_" + state.nextLocalId++,
      role: "user",
      content: text.trim(),
      message_chain: [{ type: "Plain", text: text.trim() }],
      timestamp: new Date().toISOString(),
      is_final: true,
    };
    addMessage(localMsg);

    state.ws.send(
      JSON.stringify({
        type: "message",
        message: [{ type: "Plain", text: text.trim() }],
        stream: true,
      }),
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
    fetch(url)
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
      "/api/v1/pipelines/" +
      CONFIG.pipelineUuid +
      "/ws/reset/" +
      CONFIG.sessionType;
    fetch(url, { method: "POST" })
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
    bubble.innerHTML = isUser
      ? esc(msg.content || extractText(msg))
      : renderMarkdown(msg.content || extractText(msg));

    // Meta row: time + powered by
    var meta = document.createElement("div");
    meta.className = "lb-msg-meta";

    var time = document.createElement("span");
    time.className = "lb-msg-time";
    time.textContent = formatTime(msg.timestamp);
    meta.appendChild(time);

    body.appendChild(bubble);
    body.appendChild(meta);

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

  function updateMessageEl(idx, msg) {
    var allMsgs = els.messages.querySelectorAll(".lb-msg");
    if (allMsgs[idx]) {
      var bubble = allMsgs[idx].querySelector(".lb-msg-bubble");
      if (bubble) {
        bubble.innerHTML = renderMarkdown(msg.content || extractText(msg));
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
      loadHistory();
      wsConnect();
      setTimeout(function () {
        if (els.input) els.input.focus();
      }, 300);
    } else {
      els.panel.classList.remove("lb-visible");
      els.bubble.classList.remove("lb-open");
    }
  }

  function handleSend() {
    var text = els.input.value;
    if (!text.trim() || !state.isConnected) return;

    sendMessage(text);
    els.input.value = "";
    els.input.style.height = "auto";
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
