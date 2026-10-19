# Conectar tu instalación con la web pública

La web funciona en https://6abinsky.github.io/met4tron/ y se consulta sin instalar Streamlit.

Para enviar datos desde el ZIP anterior:
1. Cierra Streamlit.
2. Descarga `cliente/integraciones.py` de este repositorio y reemplaza `metatron_core/integraciones.py` en tu carpeta de instalación.
3. Inicia MET4TRON y configura `6abinsky/met4tron` con tu token local.
4. Genera y envía el informe de 24 horas. El paquete incluye los últimos siete días para búsquedas.

No pulses «Instalar o actualizar publicación automática» en el ZIP anterior: la web ya está configurada en GitHub. Este archivo de conexión conserva las funciones de mensajería existentes y cambia los envíos a borradores de Releases, visibles únicamente con permisos adecuados. No publiques manualmente esos borradores.

La web publica a las 20:00 de Bolivia; los envíos posteriores se procesan al ejecutar el workflow. Sin lotes muestra un estado vacío. GitHub puede retrasar el horario programado.
