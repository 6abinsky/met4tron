# MET4TRON

Monitoreo y análisis de publicaciones públicas de Bolivia. Proyecto de 6abinsky.

## Función de este repositorio

Repositorio privado de recepción y publicación. Streamlit se ejecuta en Linux Mint; la base SQLite, las sesiones y las claves de IA permanecen en el equipo local. No subas el ZIP completo de instalación.

- `github_publicar.py`: recibe el paquete web desde Releases, respeta la fecha de publicación y conserva siete días de publicaciones.
- `.github/workflows/publicar.yml`: prepara y publica mediante GitHub Pages a las 20:00 de Bolivia (00:00 UTC). GitHub puede retrasar ejecuciones programadas.
- `.gitignore`: excluye bases de datos y configuración privada; no sustituye una revisión antes de subir archivos.

## Conectar Streamlit

En Configuración GitHub de MET4TRON, usa `6abinsky/met4tron`. Guarda el token únicamente en tu instalación local. El envío crea un Release privado `datos-*` con el archivo `metatron-web.zip`, que contiene los recursos web y los datos seleccionados; no envía SQLite ni claves de IA.

El programa y workflow ya están instalados. No es necesario volver a instalarlos desde la aplicación. Sin lotes, el workflow termina correctamente sin desplegar.

## Activar la web

En Settings → Pages, selecciona GitHub Actions como fuente. La disponibilidad de Pages en repositorios privados depende del plan de GitHub; si GitHub solicita un cambio de plan, no hagas público este repositorio para evitar exponer lotes pendientes. La activación de Pages aún debe completarse y verificarse.

Tras enviar el primer lote desde MET4TRON, el workflow podrá publicar a partir de su fecha `publicar_desde`. Comprueba el resultado en Actions. La instalación del workflow por sí sola no significa que la web ya esté publicada.

## Linux Mint y base anterior

Utiliza `instalar_linux_mint.sh` e `iniciar_linux.sh` del paquete local entregado. Con la aplicación anterior cerrada, conserva una copia de `met4tron_flex_data` y señala esa carpeta al configurador. No pegues el contenido de SQLite dentro de un archivo Python. La migración crea un respaldo y conserva la tabla antigua.

## Datos y donaciones

Los datos se reciben como assets de Releases privados, no en commits. El workflow recorta publicaciones de más de siete días y retira el reporte cuando supera 24 horas. La actualización manual del campo `monto` reutiliza datos ya publicados; requiere una web previamente desplegada.
