---
name: informe-contrato-html
description: 'Genera el informe HTML final de una revisión de contrato (resumen, puntos clave, riesgos, mejoras) a partir de fragmentos JSON mediante un renderizador determinista que escapa el contenido y verifica las citas contra el texto del contrato. Use when: crear informe html, reporte de contrato, renderizar resultados del análisis, esquema JSON del informe.'
---

# Informe HTML de contrato

El informe se genera con un script, no escribiendo HTML a mano: garantiza formato uniforme, escapa el contenido del contrato (seguridad) y comprueba que las citas existen en el texto.

## Flujo

1. Cada especialista escribe un fragmento JSON en `informes/.trabajo/<slug>/` (`resumen.json`, `riesgos.json`, `mejoras.json`). El orquestador añade `meta.json` y `veredicto.json`. Esquema completo y reglas de validación: [esquema-json.md](./references/esquema-json.md). Ejemplo: [ejemplo.json](./assets/ejemplo.json).
   Cada especialista valida su propio fragmento antes de terminar:
   `python3 .github/skills/informe-contrato-html/scripts/render_report.py --fragmento <resumen|riesgos|mejoras> --texto informes/.trabajo/<slug>/texto.txt <su.json> [riesgos.json]`.
2. **Validar** antes de renderizar (no genera HTML; mismas comprobaciones que el renderizado):
   ```
   python3 .github/skills/informe-contrato-html/scripts/render_report.py --validar \
     --texto informes/.trabajo/<slug>/texto.txt \
     informes/.trabajo/<slug>/meta.json informes/.trabajo/<slug>/resumen.json \
     informes/.trabajo/<slug>/riesgos.json informes/.trabajo/<slug>/mejoras.json \
     informes/.trabajo/<slug>/veredicto.json
   ```
   Salida `1` = error estructural (enum inválido, ids duplicados, referencias rotas...): corregir el fragmento indicado. Salida `3` = avisos de calidad (citas no verificadas o demasiado cortas, riesgos `medio`+ sin mejora, veredicto inferior al riesgo máximo, > 20 riesgos): corregirlos, no ignorarlos. También avisa de citas situadas en otra página que la indicada en `clausula` y de recuentos del veredicto que no cuadran.
3. **Renderizar** (mismos argumentos, cambiando `--validar` por `--salida informes/<slug>-informe.html`). El script no acepta nada sin `--texto` sin avisar de que las citas no se han verificado. Los fragmentos se fusionan por clave de primer nivel.
4. Si tras corregir queda un aviso que es un falso positivo justificado (p. ej. cita con salto de columna en el PDF), usar `--permisivo` y mencionarlo en `advertencias`; nunca para dejar citas inventadas.
5. Comunicar al usuario la ruta del HTML generado (se abre en cualquier navegador; es autocontenido y apto para imprimir/PDF).

Opciones del renderizador: `--anonimizar` enmascara DNI/NIE e IBAN en el HTML (para compartirlo); `--permisivo` ver arriba. El HTML es autocontenido (CSS en `assets/estilo.css` y JS en `assets/informe.js`, incrustados al generar): tarjetas plegables, filtro por severidad, enlaces riesgo ↔ mejora, copiar redacciones, tema claro/oscuro e impresión con todo desplegado.

Scripts de gestión (todos con la biblioteca estándar):
- `scripts/preparar_revision.py "<pdf>"`: calcula slug, versión (`-v2`, `-v3`...), versión anterior, SHA-256 del PDF y si cambió; crea la carpeta de trabajo. Reutiliza la última carpeta si quedó sin informe.
- `scripts/integridad.py guardar|comprobar <slug>`: instantánea por hash antes y después de delegar; detecta ficheros tocados fuera de la revisión (incluidas versiones anteriores).
- `scripts/regenerar_todos.py [--solo slug...] [--anonimizar]`: vuelve a renderizar todos los informes desde sus fragmentos (p. ej. tras cambiar el diseño).

Para comparar dos revisiones del mismo contrato (qué riesgos son nuevos, cambios de severidad y de datos clave, si el texto cambió): `python3 .github/skills/informe-contrato-html/scripts/comparar_versiones.py informes/.trabajo/<anterior> informes/.trabajo/<nueva> [--salida informes/<slug>-cambios.md]`; con `--paginas` devuelve solo las páginas del texto que cambiaron (JSON).

Solo requiere la biblioteca estándar de Python 3. Pruebas: `.venv/bin/python -m unittest discover -s .github/skills/informe-contrato-html/tests` y `... -s .github/skills/extraer-texto-pdf/tests` (esta última necesita pypdf).
