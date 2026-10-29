# Complemento de generación de imágenes AI

## Introducción

Un complemento de dibujo compatible con el formato API de generación de imágenes OpenAI. Admite cualquier servicio compatible con la API de generación de imágenes OpenAI.

## Características

- ✅ Totalmente compatible con el formato API de generación de imágenes OpenAI
- 🎨 Admite punto final API personalizado y nombre de modelo
- 📐 Admite múltiples relaciones de aspecto de imagen
- 🔧 Opciones de configuración flexibles

## Guía de configuración

### Configuración de API

-**Punto final API**: el valor predeterminado es`https://api.qhaigc.net`, se puede personalizar para cualquier punto final API compatible con estilo OpenAI
-**Clave API**: obtenga su clave API desde [https://api.qhaigc.net/console/token](https://api.qhaigc.net/console/token)
-**Nombre del modelo**: puede establecer un nombre de modelo personalizado, el valor predeterminado es`qh-draw-x1-pro`

### Opciones de tamaño de imagen

Se admiten los siguientes tamaños de imagen:

- Cuadrado 1:1 (1024x1024)
- Cuadrado 1:1 (1280x1280)
- Retrato 3:5 (768x1280)
- Paisaje 5:3 (1280x768)
- Retrato 9:16 (720x1280)
- Paisaje 16:9 (1280x720)
- Paisaje 4:3 (1024x768)
- Retrato 3:4 (768x1024)

## Uso

Utilice el comando`!draw`para generar imágenes:

```bash
# Generate an image
!draw a beautiful sunset landscape
!draw a cat sitting on a rainbow
```

## Pasos de instalación

1. Instale este complemento desde la página de administración de complementos de LangBot.
2. Obtenga su clave API: [https://api.qhaigc.net/console/token](https://api.qhaigc.net/console/token)
3. Complete la clave API en la configuración del complemento.
4. (Opcional) Configure el punto final de API, el nombre del modelo y el tamaño de imagen predeterminado

## Modelos compatibles

### Serie Nano Plátano

-**Nano Banana 1**(lanzado en agosto de 2025): un modelo de generación de imágenes de Google DeepMind, basado en la arquitectura Flash Gemini 2.5 con parámetros de 450M a 8B. Los puntos fuertes principales son la coherencia de roles, la fusión de múltiples imágenes y la edición local. Lidera la clasificación de edición de imágenes de LMArena con una puntuación de 1362 y se utiliza ampliamente en comercio electrónico, diseño, educación y más.

-**Nano Banana 2**(lanzado en noviembre de 2025): una actualización integral de la primera generación, que admite resolución nativa de 2K, con superresolución 4K opcional. La velocidad de generación se mejora en un 300%, permitiendo escenas complejas en solo 10 segundos. Grandes avances en la representación de textos chinos y la derivación de fórmulas matemáticas. Entiende la lógica física y el conocimiento del mundo, utilizando una arquitectura híbrida de "cognición + generación" que revoluciona la productividad de las industrias creativas.

### Serie de dibujos de IA de Qihang

-**qh-draw-3d**: se centra en generar imágenes de estilo 3D populares, caracterizadas por delicados modelos 3D y fuertes efectos visuales 3D.
-**qh-draw-4d**: se centra en generar imágenes de estilo 4D populares, con modelos 4D sofisticados y elementos visuales cercanos a la realidad pero no fotografías reales.
-**qh-draw-x1-pro**: modelo Qihang AI Drawing x1-pro, basado en modelos SD de código abierto con comprensión del lenguaje natural.
-**qh-draw-x2-preview**: Modelo de dibujo profesional de desarrollo propio V2.0. Basado en x1-pro, mejora la comprensión del lenguaje y las capacidades integrales de dibujo, lo que lo hace adecuado para más tareas.
-**qh-draw:Korean-comic-style**: se especializa en generar imágenes clásicas de estilo cómic coreano en 2D, con colores brillantes, líneas suaves y un ambiente de escena preciso para los cómics coreanos.

### Lista de modelos disponibles

`nano-banana-1`,`nano-banana-2`,`qh-draw-3d`,`qh-draw-4d`,`qh-draw-x1-pro`,`qh-draw-x2-preview`,`qh-draw: estilo cómic coreano`

## Compatibilidad

Este complemento es compatible con cualquier servicio que siga la especificación API de generación de imágenes de OpenAI, incluidos, entre otros:

-OpenAI DALL-E 3
- Otros servicios de generación de imágenes compatibles con el formato OpenAI

## Licencia

MI licencia
