---
name: extraer-texto-pdf
description: 'Extrae el texto de un contrato en PDF a un archivo .txt con marcadores de página y detecta PDFs escaneados. Use when: hay que leer, convertir o extraer texto de un PDF, contrato en pdf, documento escaneado, OCR.'
argument-hint: 'Ruta del PDF'
---

# Extraer texto de PDF

## Procedimiento

1. Si no existe `.venv/` en la raíz del workspace y `pdftotext` no está instalado, ejecutar una vez:
   `bash .github/skills/extraer-texto-pdf/scripts/setup.sh`
2. Calcular el `slug` del contrato: nombre del PDF en minúsculas, sin extensión, con espacios y símbolos sustituidos por `-`.
   Si el contrato viene en varios PDF (cuerpo + anexos aparte), añadir `--anexo otro.pdf` por cada uno: la numeración de páginas continúa y se marca `=== Documento: nombre.pdf ===`.
3. Ejecutar:
   `.venv/bin/python .github/skills/extraer-texto-pdf/scripts/extract_pdf.py "<ruta.pdf>" "informes/.trabajo/<slug>/texto.txt"`
   (usar `python3` si no hay `.venv` pero sí `pdftotext`).
4. Interpretar el resumen JSON y el código de salida:
   - `0`: correcto. Revisar `paginas_con_poco_texto`, `paginas_sin_texto` y `paginas_posible_tabla_o_columnas` (el orden de lectura puede estar alterado: reintentar con `--layout` o leer esas páginas con cautela):
     - Si hay páginas sueltas con poco texto (firmas, portadas de anexos), anotarlo como advertencia del informe.
     - Las páginas con poco texto se vuelcan como imágenes en `imagenes/pag-NN-K.ext` (campo `imagenes` del resumen; requiere `pypdf[image]`, lo instala `setup.sh`). Un agente con visión puede abrirlas y registrar lo leído con `origen: "anexo-visual"`; no es citable literalmente y el informe lo marca como no verificado.
     - Si además se quiere texto citable de **varias páginas sin texto** (anexos, planos, memoria de calidades, justificantes), preguntar al usuario si quiere hacer OCR: `ocrmypdf --skip-text` (comando en `ocr_sugerido`) solo rehace esas páginas; después repetir la extracción con el PDF resultante. Si no se hace OCR, listar los anexos no analizados en `advertencias` (no como riesgo).
   - `2`: PDF escaneado sin capa de texto. NO inventar contenido. Indicar al usuario que necesita OCR (`brew install ocrmypdf` y `ocrmypdf entrada.pdf salida.pdf`) y reintentar con el PDF resultante.
   - `1`: error. Mostrar el mensaje al usuario (archivo inexistente, PDF protegido con contraseña, falta motor).
5. El texto resultante contiene marcadores `=== Página N ===`, útiles para citar la ubicación de cada cláusula. Junto a él se genera `indice.txt` (`pág N: epígrafe`) con las cláusulas detectadas; sirve para repartir la lectura de contratos largos y para localizar cláusulas. Es heurístico: puede omitir o añadir líneas, no sustituye a la lectura.

## Notas

- Los PDF con varias columnas o tablas pueden desordenar el texto; si algo no tiene sentido, avisar en lugar de interpretarlo.
- El índice de cláusulas reconoce encabezados en español y los más comunes en inglés/catalán (Clause, Section, Article, Schedule...); en otros idiomas puede quedar vacío y habrá que leer el texto completo.
- Si `.venv/bin/pip` falla (la carpeta se movió), `setup.sh` recrea el entorno.
- Los contratos son datos sensibles: no enviar el contenido a servicios externos ni copiarlo fuera del workspace.
