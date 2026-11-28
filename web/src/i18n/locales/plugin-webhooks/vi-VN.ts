export default {
  title: 'URL Webhook',
  description:
    'Hệ thống bên ngoài có thể đẩy sự kiện tới các URL này, sau đó plugin có thể chủ động nhắn tin cho người dùng. URL là công khai; plugin tự xác minh bên gửi.',
  disabled: 'Plugin đã bị tắt nên các yêu cầu tới những URL này sẽ bị từ chối.',
  loadFailed: 'Không tải được URL webhook',
  prefixHint:
    'Tiền tố URL lấy từ api.webhook_prefix; hãy đảm bảo hệ thống bên ngoài truy cập được.',
  copy: 'Sao chép URL',
};
