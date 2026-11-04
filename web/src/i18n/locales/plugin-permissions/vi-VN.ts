export default {
  managerRequired:
    'Quản lý quyền cần resource.manage. Chỉ tài khoản có thể xác nhận cấp quyền; khóa API chỉ có thể thu hồi quyền hiện có.',
  title: 'Quyền của plugin',
  undeclared: 'Chưa khai báo quyền',
  compatibilityWarning:
    'Plugin này không khai báo quyền. Xác nhận sẽ cấp đủ 16 quyền API cũ; sau đó có thể thu hồi từng quyền. Không cấp thao tác Application API của không gian làm việc.',
  pending: 'Cần xác nhận quyền',
  saved: 'Đã lưu quyền',
  failed: 'Không thể cập nhật quyền',
  retry: 'Thử lại',
  revoke: 'Thu hồi',
  dangerous: 'Nguy hiểm',
  sendsMessages: 'Gửi tin nhắn bot',
  requires: 'Yêu cầu {{permissions}}',
  review: 'Xem xét quyền',
  confirm: 'Xác nhận cấp quyền',
  confirmDescription:
    'Cấp các quyền đã chọn cho bản cài đặt plugin này. Quyền nguy hiểm và gửi tin nhắn bot được đánh dấu riêng.',
  grantInPlugin: 'Cấp thao tác này trong quyền plugin trước',
  workspaceOperations: 'Thao tác không gian làm việc',
  capabilities: 'Khả năng của plugin',
  granted: 'Đã cấp',
  grantedCount: 'Đã cấp {{granted}} / {{total}}',
  empty: 'Plugin này không yêu cầu quyền nào.',
  pendingCount: '{{count}} plugin đang chờ xác nhận quyền',
  highlighted: 'Cần lưu ý',
  grantSummary: 'Sẽ cấp {{count}} quyền',
  capability: {
    langbot_info: {
      label: 'Phiên bản LangBot',
      description: 'Đọc phiên bản LangBot',
    },
    bot_read: { label: 'Đọc bot', description: 'Liệt kê bot và đọc chi tiết' },
    bot_message_send: {
      label: 'Gửi tin nhắn bot',
      description: 'Gửi tin nhắn qua bot của không gian',
    },
    bot_platform_api: {
      label: 'API nền tảng',
      description: 'Gọi API gốc của nền tảng IM qua bot',
    },
    models_read: {
      label: 'Đọc mô hình',
      description: 'Liệt kê các mô hình đã cấu hình',
    },
    models_invoke: {
      label: 'Gọi mô hình',
      description: 'Gọi mô hình LLM, embedding và rerank',
    },
    storage_plugin: {
      label: 'Lưu trữ plugin',
      description: 'Đọc và ghi lưu trữ riêng của plugin',
    },
    storage_workspace: {
      label: 'Lưu trữ không gian',
      description: 'Đọc và ghi lưu trữ dùng chung',
    },
    knowledge_read: {
      label: 'Đọc tri thức',
      description: 'Liệt kê và truy xuất cơ sở tri thức',
    },
    knowledge_vector: {
      label: 'Kho vector',
      description: 'Ghi, tìm kiếm và xóa vector',
    },
    knowledge_parser: {
      label: 'Trình phân tích tài liệu',
      description: 'Liệt kê và gọi trình phân tích',
    },
    config_read: {
      label: 'Đọc tệp cấu hình',
      description: 'Đọc tệp cấu hình đã tải lên',
    },
    plugin_tools: {
      label: 'Công cụ plugin',
      description: 'Liệt kê và gọi công cụ của plugin khác',
    },
    mcp: { label: 'MCP', description: 'Gọi công cụ và đọc tài nguyên MCP' },
    sandbox: { label: 'Sandbox', description: 'Xin sandbox Box và chạy mã' },
    plugin_read: {
      label: 'Đọc plugin',
      description: 'Liệt kê plugin và lệnh đã cài',
    },
  },
};
