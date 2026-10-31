# Traducción automática

Detecta automáticamente mensajes en idiomas extranjeros en chats grupales y tradúcelos usando LLM.

## Características

- 🌐 Detecta automáticamente el idioma de los mensajes: no se necesitan comandos manuales
- 🤖 Utiliza LLM para traducciones naturales y de alta calidad
- ⚙️ Idioma de destino configurable (chino, inglés, japonés, coreano, francés, español)
- 📏 Omite mensajes cortos, emoticones y URL
- 🔇 Solo traduce cuando es necesario; los mensajes en el mismo idioma se ignoran
- 👥 Solo grupo de forma predeterminada, soporte de chat privado opcional

## Cómo funciona

1. Cuando se recibe un mensaje en un chat grupal, el complemento envía el texto a un LLM
2. El LLM detecta si el mensaje está en un idioma diferente al objetivo configurado.
3. Si se necesita traducción, el complemento responde con el texto traducido con el prefijo 🌐
4. Los mensajes que ya están en el idioma de destino se ignoran silenciosamente.

## Configuración

| Opción | Descripción | Predeterminado |
|---|---|---|
| Idioma de destino | Idioma a traducir | Chino (simplificado) |
| Modelo LLM | modelo a utilizar para traducción | Primero disponible |
| Longitud mínima del texto | Saltar mensajes más cortos que este | 4 caracteres |
| Habilitar en chat privado | Traducir también mensajes privados | Apagado |
