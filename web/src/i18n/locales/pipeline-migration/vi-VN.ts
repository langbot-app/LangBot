export default {
  complete: 'Hoàn tất',
  checkingPlugin: 'Kiểm tra plugin',
  preparingPlugin: 'Chuẩn bị cài đặt',
  installDetails: 'Chi tiết cài đặt',
  stageProgress: 'Tiến độ từng giai đoạn',
  downloaded: 'Đã tải {{size}}',
  processed: 'Đã xử lý {{completed}} / {{total}} pipeline',
  installErrors: {
    plugin_version_unavailable:
      'Phiên bản cần thiết chưa có trên chợ. Thử lại sau khi phát hành hoặc chỉ chuyển dữ liệu.',
    plugin_download_timeout:
      'Tải plugin quá thời gian chờ. Kiểm tra mạng rồi thử lại.',
    plugin_marketplace_unavailable:
      'Chợ chưa thể cung cấp gói plugin. Vui lòng thử lại sau.',
    plugin_download_failed: 'Không thể tải plugin. Vui lòng kiểm tra mạng.',
    dependency_prepare_failed:
      'Không thể cài các thư viện phụ thuộc. Kiểm tra môi trường chạy.',
    plugin_launch_failed:
      'Không thể khởi động plugin. Kiểm tra môi trường chạy.',
  },
  autoDescription:
    'Các runner cũ đã chuyển thành plugin. Chuyển đổi tất cả pipeline và giữ lại thiết lập. Cấu hình cũ sẽ được sao lưu; hội thoại sẽ bắt đầu lại.',
  viewPipelines: 'Xem pipeline',
  autoInstall: 'Cài plugin và chuyển đổi',
  dataOnly: 'Chỉ chuyển đổi dữ liệu',
  dataOnlyHint:
    'Dành cho mạng nội bộ hoặc ngoại tuyến. Tự cài các plugin runner tương ứng sau khi chuyển đổi.',
  installing: 'Đang cài plugin cần thiết…',
  migrating: 'Đang chuyển đổi pipeline…',
  summary: 'Đã chuyển {{migrated}}; {{remaining}} cần xử lý.',
  installFailed:
    'Cài đặt thất bại. Mở chi tiết để xem giai đoạn lỗi rồi thử lại, hoặc chỉ chuyển dữ liệu.',

  activationRetryHint:
    'Sau khi kiểm tra môi trường chạy, làm mới, chọn pipeline này và xác nhận để chỉ thử kích hoạt lại. Cấu hình đã lưu sẽ không được di chuyển lần nữa.',
  details: 'Chi tiết chuyển đổi',
  notices: {
    runtimeUnavailable:
      'Môi trường chạy plugin bị ngắt kết nối. Khôi phục kết nối rồi thử lại, hoặc chỉ di chuyển dữ liệu.',
    executionFailed:
      'Di chuyển thất bại. Kiểm tra nhật ký máy chủ rồi thử lại.',
    pluginRequired:
      'Cài đặt hoặc bật plugin runner ở trên, rồi làm mới bản xem trước.',
    legacyArchive:
      'Cấu hình hoạt động chỉ giữ Runner đã chọn. Tất cả thiết lập Runner cũ, kể cả các thiết lập không dùng, được giữ trong bản sao lưu di chuyển.',
    contextDefaults:
      'Lịch sử sẽ dùng ngân sách ngữ cảnh và thiết lập tóm tắt mới thay vì giới hạn số lượt cố định.',
    modelReasoning:
      'Thiết lập suy luận của từng mô hình được giữ lại và do máy chủ áp dụng.',
    serialTools: 'Các công cụ vẫn được gọi lần lượt sau khi di chuyển.',
    retrievalDefaults:
      'Truy xuất dùng giới hạn top-k và độ dài kết quả mới. Hãy kiểm tra sau khi di chuyển.',
    boxReset:
      'Giữ nguyên cấu hình tái sử dụng sandbox. Không chuyển trạng thái container cũ; sandbox mới dùng cùng quy tắc tái sử dụng.',
    persistentHistory:
      'Hội thoại mới dùng lịch sử bền vững và riêng biệt. Lịch sử từ xa cũ không được nhập.',
    tweaksDefault: 'Langflow tweaks mặc định là một đối tượng rỗng.',
    timeoutDefault: 'Dify mặc định có thời gian chờ yêu cầu là 30 giây.',
    historyReset:
      'Lịch sử và mã phiên cũ không được chuyển. Hội thoại mới sẽ bắt đầu sau khi di chuyển.',
    sessionTitle: 'Phiên WeKnora mới dùng tiêu đề do plugin tạo.',
    aliasRepaired: 'Tên trường cũ được ánh xạ sang tên đang được hỗ trợ.',
    nullDefault: 'Giá trị trống này sẽ dùng giá trị mặc định của plugin mới.',
    outputPolicy: 'Thiết lập hiển thị nội dung suy luận hiện tại được giữ lại.',
    filteredVariables:
      'Chỉ chuyển các biến được hỗ trợ; biến dành riêng do ngữ cảnh hội thoại cung cấp.',
    identityPreserved:
      'Danh tính người dùng phía nhà cung cấp giữ nguyên nguồn cũ.',
    newDefaults:
      'Tùy chọn mới dùng giá trị mặc định đã mô tả; các giá trị cũ được hỗ trợ vẫn được giữ.',
    externalState:
      'Hoàn tất hoặc hủy các tương tác từ xa đang chờ trước khi di chuyển; trạng thái đang chạy không được chuyển.',
    pluginVersion:
      'Cài phiên bản plugin được yêu cầu rồi làm mới. Phiên bản cũ không hỗ trợ lần di chuyển này.',
    schemaChanged:
      'Cấu hình Runner đã cài không khớp với đích di chuyển. Kiểm tra phiên bản plugin rồi làm mới.',
    runnerExcluded:
      'Pipeline này loại trừ plugin Runner cần thiết. Hãy chỉnh thiết lập tiện ích trước.',
    boxTemplateInvalid:
      'Mẫu tái sử dụng không hợp lệ. Dùng {tên_biến}; không hỗ trợ trường vị trí, chuyển đổi định dạng hoặc truy cập thuộc tính.',
    pendingInteraction:
      'Có hội thoại đang chờ nhập liệu. Hãy hoàn tất hoặc hủy trước khi di chuyển.',
  },
  title: 'Di chuyển pipeline',
  description:
    'Chọn các pipeline cần chuyển đổi. Cấu hình cũ sẽ được sao lưu; các cuộc trò chuyện sẽ bắt đầu lại.',
  detected: '{{count}} pipeline cần xem xét di chuyển.',
  review: 'Xem xét di chuyển',
  readOnly:
    'Chỉ người có quyền quản lý không gian mới được di chuyển pipeline.',
  previewError: 'Không lấy được bản xem trước. Hãy làm mới.',
  submitting: 'Đang gửi các pipeline đã chọn…',
  running: 'Đang di chuyển. Đóng hộp thoại không hủy tác vụ.',
  finished: 'Tác vụ đã kết thúc. Hãy kiểm tra kết quả từng pipeline.',
  failed: 'Tác vụ thất bại. Hãy kiểm tra kết quả từng pipeline.',
  lost: 'Mất theo dõi tác vụ; chưa biết kết quả. Hãy làm mới bản xem trước trước khi thao tác tiếp.',
  requestError: 'Yêu cầu chưa hoàn tất. Làm mới bản xem trước rồi chọn lại.',
  warningFallback: 'Kiểm tra cài đặt này trước khi di chuyển.',
  blockerFallback:
    'Không thể di chuyển an toàn cài đặt hoặc trạng thái chạy này. Hãy xử lý rồi làm mới bản xem trước.',
  changedFields: 'Trường thay đổi',
  activationHint:
    'Cấu hình đã lưu nhưng đang chờ kích hoạt. Nhờ quản trị viên kiểm tra môi trường rồi làm mới. Không chạy lại di chuyển một cách mù quáng.',
  pluginHint:
    'Thiếu plugin? Cài đặt hoặc bật runner trong Tiện ích mở rộng, rồi làm mới bản xem trước.',
  extensions: 'Mở Tiện ích',
  results: 'Kết quả từng pipeline',
  selection: 'Đã chọn {{count}} (tối đa 50)',
  confirm: 'Tôi xác nhận di chuyển các pipeline đã chọn.',
  refresh: 'Làm mới bản xem trước',
  execute: 'Di chuyển đã chọn',
  legacyGate:
    'Cấu hình cũ chỉ đọc cho đến khi di chuyển. Lưu và gỡ lỗi bị tắt để tránh chuyển đổi ngầm.',
  states: {
    ready: 'Sẵn sàng',
    needs_plugin: 'Cần plugin',
    blocked: 'Bị chặn',
    already_current: 'Đã cập nhật',
    not_legacy: 'Không phải bản cũ',
    activation_pending: 'Chờ kích hoạt',
    pending: 'Đang chờ',
    migrated: 'Đã di chuyển',
    stale: 'Bản xem trước đã cũ',
    failed: 'Thất bại',
  },
};
