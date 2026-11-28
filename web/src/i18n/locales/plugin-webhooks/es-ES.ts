export default {
  title: 'URL de webhook',
  description:
    'Los sistemas externos pueden enviar eventos a estas URL y el plugin puede escribir a los usuarios de forma proactiva. Las URL son públicas; el plugin verifica a cada remitente.',
  disabled:
    'El plugin está desactivado, por lo que se rechazan las solicitudes a estas URL.',
  loadFailed: 'No se pudieron cargar las URL de webhook',
  prefixHint:
    'El prefijo de la URL proviene de api.webhook_prefix; asegúrate de que los sistemas externos puedan acceder a él.',
  copy: 'Copiar URL',
};
