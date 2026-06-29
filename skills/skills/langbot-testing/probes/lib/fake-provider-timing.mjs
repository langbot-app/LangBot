export function summarizeFakeProviderState(state) {
  if (!state) return null;
  const recentRequests = Array.isArray(state.recent_requests) ? state.recent_requests : [];
  const chatRequests = recentRequests.filter((request) => String(request?.path || "").includes("/chat/completions"));
  const successfulRequests = chatRequests.filter((request) => request?.status === "ok");
  const faultRequests = chatRequests.filter((request) => (
    request?.should_fail === true
      || request?.status === "http_fault"
      || (Number.isFinite(request?.http_status) && request.http_status >= 400)
  ));

  return {
    status: state.status || "unknown",
    url: state.url || "",
    request_count: Number.isFinite(state.request_count) ? state.request_count : recentRequests.length,
    recent_request_count: recentRequests.length,
    chat_request_count: chatRequests.length,
    fault_count: faultRequests.length,
    streamed_request_count: chatRequests.filter((request) => request?.stream === true).length,
    duration_ms: stats(chatRequests.map((request) => numberOrNull(request?.duration_ms)).filter(Number.isFinite)),
    successful_duration_ms: stats(successfulRequests.map((request) => numberOrNull(request?.duration_ms)).filter(Number.isFinite)),
    first_chunk_ms: stats(successfulRequests.map((request) => numberOrNull(request?.first_chunk_ms)).filter(Number.isFinite)),
    first_content_chunk_ms: stats(successfulRequests.map((request) => numberOrNull(request?.first_content_chunk_ms)).filter(Number.isFinite)),
    content_chunk_count: stats(successfulRequests.map((request) => numberOrNull(request?.content_chunk_count)).filter(Number.isFinite)),
    config: state.config || {},
  };
}

export function buildProviderTimingMetrics(samples, state) {
  const recentRequests = Array.isArray(state?.recent_requests) ? state.recent_requests : [];
  const byExpectedText = new Map();
  for (const request of recentRequests) {
    const expected = String(request?.expected_text || "");
    if (!expected) continue;
    if (!byExpectedText.has(expected)) byExpectedText.set(expected, []);
    byExpectedText.get(expected).push(request);
  }

  const segments = [];
  const missingExpectedText = [];
  for (const sample of samples) {
    const expected = String(sample?.expected_text || "");
    if (!expected) continue;
    const request = (byExpectedText.get(expected) || []).shift();
    if (!request) {
      missingExpectedText.push(expected);
      continue;
    }
    const segment = buildTimingSegment(sample, request);
    if (segment) segments.push(segment);
  }

  const values = (key) => segments.map((segment) => numberOrNull(segment[key])).filter(Number.isFinite);
  return {
    matched_request_count: segments.length,
    missing_provider_match_count: missingExpectedText.length,
    missing_expected_text: missingExpectedText.slice(0, 20),
    send_to_provider_start_ms: stats(values("send_to_provider_start_ms")),
    provider_duration_ms: stats(values("provider_duration_ms")),
    provider_finish_to_ws_final_ms: stats(values("provider_finish_to_ws_final_ms")),
    langbot_overhead_estimate_ms: stats(values("langbot_overhead_estimate_ms")),
    e2e_minus_provider_ms: stats(values("e2e_minus_provider_ms")),
    provider_first_content_to_ws_first_content_ms: stats(values("provider_first_content_to_ws_first_content_ms")),
    segments,
  };
}

function buildTimingSegment(sample, request) {
  const sentEpochMs = numberOrNull(sample.sent_epoch_ms);
  const finishedEpochMs = numberOrNull(sample.finished_epoch_ms);
  const providerStartedEpochMs = numberOrNull(request.started_epoch_ms);
  const providerFinishedEpochMs = numberOrNull(request.finished_epoch_ms);
  const providerFirstContentEpochMs = numberOrNull(request.first_content_chunk_epoch_ms);
  const wsFirstContentEpochMs = numberOrNull(sample.first_assistant_content_epoch_ms);
  const responseDurationMs = numberOrNull(sample.response_duration_ms);
  const providerDurationMs = numberOrNull(request.duration_ms);

  const sendToProviderStartMs = finiteDelta(providerStartedEpochMs, sentEpochMs);
  const providerFinishToWsFinalMs = finiteDelta(finishedEpochMs, providerFinishedEpochMs);
  const e2eMinusProviderMs = Number.isFinite(responseDurationMs) && Number.isFinite(providerDurationMs)
    ? rounded(responseDurationMs - providerDurationMs)
    : null;
  const overheadEstimateMs = Number.isFinite(sendToProviderStartMs) && Number.isFinite(providerFinishToWsFinalMs)
    ? rounded(sendToProviderStartMs + providerFinishToWsFinalMs)
    : e2eMinusProviderMs;

  return {
    sample_index: sample.index,
    pipeline_label: sample.pipeline_label || "",
    expected_text: sample.expected_text || "",
    provider_request_id: request.id || "",
    provider_request_number: request.request_number ?? null,
    response_duration_ms: responseDurationMs,
    provider_duration_ms: providerDurationMs,
    send_to_provider_start_ms: sendToProviderStartMs,
    provider_finish_to_ws_final_ms: providerFinishToWsFinalMs,
    langbot_overhead_estimate_ms: overheadEstimateMs,
    e2e_minus_provider_ms: e2eMinusProviderMs,
    provider_first_content_to_ws_first_content_ms: finiteDelta(wsFirstContentEpochMs, providerFirstContentEpochMs),
    provider_status: request.status || "",
    provider_http_status: request.http_status ?? null,
  };
}

function finiteDelta(left, right) {
  return Number.isFinite(left) && Number.isFinite(right) ? rounded(left - right) : null;
}

export function stats(values) {
  if (values.length === 0) return { min: 0, p50: 0, p95: 0, p99: 0, max: 0 };
  return {
    min: rounded(Math.min(...values)),
    p50: percentile(values, 50),
    p95: percentile(values, 95),
    p99: percentile(values, 99),
    max: rounded(Math.max(...values)),
  };
}

export function percentile(values, percentileValue) {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.ceil((percentileValue / 100) * sorted.length) - 1);
  return rounded(sorted[index]);
}

export function rounded(value) {
  return Number(value.toFixed(3));
}

function numberOrNull(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}
