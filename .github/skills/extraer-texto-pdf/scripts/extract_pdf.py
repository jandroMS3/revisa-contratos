#!/usr/bin/env python3
"""Extrae el texto de un PDF a un .txt con marcadores de página.

Uso: extract_pdf.py <entrada.pdf> <salida.txt> [--anexo otro.pdf ...] [--layout] [--sin-imagenes]
  --anexo  PDF adicional del mismo contrato (anexos en fichero aparte): sus páginas continúan la numeración
           y se marcan con `=== Documento: nombre.pdf ===` antes de la primera.

Escribe también `indice.txt` junto a la salida (cláusulas/epígrafes detectados con su página)
y, para las páginas con poco o ningún texto (anexos, planos, justificantes), vuelca las imágenes
incrustadas en `imagenes/pag-NN-K.ext` junto a la salida para que un agente con visión pueda leerlas
(requiere `pypdf[image]`, ver setup.sh). `--layout` usa el modo layout de pypdf (mejor para tablas).
Imprime por stdout un resumen JSON. Códigos de salida:
  0 = texto extraído correctamente (revisar `paginas_sin_texto`: pueden ser anexos en imagen)
  2 = PDF sin capa de texto suficiente (probablemente escaneado, requiere OCR)
  1 = error (archivo inexistente, sin motor de extracción, PDF protegido...)
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

MIN_CHARS_PER_PAGE = 80
EMPTY_PAGE_CHARS = 20
SHORT_LINE = 30  # líneas más cortas suelen indicar columnas o tablas desordenadas
MIN_LINES_TABLE = 15

ORDINALES = (
    r"PRIMER[AO]|SEGUND[AO]|TERCER[AO]|CUART[AO]|QUINT[AO]|SEXT[AO]|S[ÉE]PTIM[AO]|OCTAV[AO]|NOVEN[AO]|"
    r"D[ÉE]CIM[AO]\w*|VIG[ÉE]SIM[AO]\w*|[ÚU]LTIM[AO]"
)
HEADING = re.compile(
    r"^\s*(?:"
    r"(?i:CL[ÁA]USULA|ESTIPULACI[ÓO]N|ART[ÍI]CULO|CAP[ÍI]TULO|ANEXO|ADENDA|EXPONEN|MANIFIESTAN|REUNIDOS|COMPARECEN)\b.*"
    rf"|(?i:{ORDINALES})\b\s*[.\-–:].*"
    r"|\d{1,2}\s*[.)]\s+[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9 ,.;:()/\-]{3,}"  # "4. PLAZO DE ENTREGA" (título en mayúsculas)
    r"|\d{1,2}\.\d{1,2}\.?\s+[A-ZÁÉÍÓÚÑ][^\n]{3,}"  # "4.1 Plazo..." (subcláusula numerada)
    r"|(?i:CLAUSE|SECTION|ARTICLE|SCHEDULE|APPENDIX|EXHIBIT|CL[ÀA]USULA|ANNEX)\s+[\dIVXA-Z]+\b.*"  # contratos en inglés/catalán
    r")\s*$"
)


def with_pdftotext(path: Path):
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    out = subprocess.run(
        [exe, "-layout", "-enc", "UTF-8", str(path), "-"],
        capture_output=True, check=True,
    ).stdout.decode("utf-8", errors="replace")
    pages = out.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return "pdftotext", pages


def with_pypdf(path: Path, layout: bool = False):
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    reader = PdfReader(str(path))
    if reader.is_encrypted and not reader.decrypt(""):
        raise RuntimeError("El PDF está protegido con contraseña.")
    mode = {"extraction_mode": "layout"} if layout else {}
    return ("pypdf-layout" if layout else "pypdf"), [(page.extract_text(**mode) or "") for page in reader.pages]


def build_index(pages):
    """Lista `pág N: epígrafe` de las cláusulas detectadas, para localizar y repartir la lectura."""
    lines = []
    for n, text in enumerate(pages, start=1):
        for raw in text.splitlines():
            line = " ".join(raw.split())
            if 4 <= len(line) <= 110 and HEADING.match(line):
                lines.append(f"pág {n}: {line}")
    return lines


def pages_maybe_tables(pages):
    """Páginas con muchas líneas cortas: posibles tablas o columnas cuyo orden de lectura puede estar alterado."""
    found = []
    for n, text in enumerate(pages, start=1):
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if len(lines) >= MIN_LINES_TABLE and sum(len(ln) < SHORT_LINE for ln in lines) / len(lines) > 0.6:
            found.append(n)
    return found


def dump_images(entradas, out_dir: Path):
    """Vuelca las imágenes incrustadas. `entradas` = [(pág. global, pdf, pág. local)]. Devuelve ({pág: [rutas]}, error|None)."""
    try:
        from pypdf import PdfReader
        lectores = {}
        result = {}
        for n, src, local in entradas:
            if src not in lectores:
                lectores[src] = PdfReader(str(src))
                if lectores[src].is_encrypted:
                    lectores[src].decrypt("")
            for k, img in enumerate(lectores[src].pages[local - 1].images, start=1):
                ext = Path(img.name).suffix or ".png"
                out_dir.mkdir(parents=True, exist_ok=True)
                target = out_dir / f"pag-{n:02d}-{k}{ext}"
                target.write_bytes(img.data)
                result.setdefault(n, []).append(str(target))
        return result, None
    except Exception as exc:  # noqa: BLE001
        return {}, f"no se pudieron extraer imágenes ({exc}); ejecuta setup.sh para instalar pypdf[image]"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entrada")
    ap.add_argument("salida")
    ap.add_argument("--anexo", action="append", default=[], help="PDF adicional del mismo contrato (repetible)")
    ap.add_argument("--layout", action="store_true", help="modo layout de pypdf (tablas); pdftotext ya usa -layout")
    ap.add_argument("--sin-imagenes", action="store_true", help="no volcar las imágenes de páginas sin texto")
    args = ap.parse_args()
    src, dst = Path(args.entrada), Path(args.salida)
    documentos = [src] + [Path(a) for a in args.anexo]
    for d in documentos:
        if not d.is_file():
            print(f"No existe el archivo: {d}", file=sys.stderr)
            return 1

    pages, origenes, inicios = [], [], {}  # origenes[i] = (pdf, pág. local) de la página global i+1
    method = None
    for d in documentos:
        try:
            result = with_pdftotext(d) or with_pypdf(d, args.layout)
        except Exception as exc:  # noqa: BLE001
            print(f"Error al leer el PDF {d}: {exc}", file=sys.stderr)
            return 1
        if result is None:
            print(
                "No hay motor de extracción. Ejecuta: "
                "bash .github/skills/extraer-texto-pdf/scripts/setup.sh",
                file=sys.stderr,
            )
            return 1
        method, doc_pages = result
        if d is not documentos[0]:
            inicios[len(pages) + 1] = d.name
        origenes += [(d, i) for i in range(1, len(doc_pages) + 1)]
        pages += doc_pages

    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8") as fh:
        for n, text in enumerate(pages, start=1):
            if n in inicios:
                fh.write(f"=== Documento: {inicios[n]} ===\n")
            fh.write(f"=== Página {n} ===\n{text.strip()}\n\n")

    low = [n for n, t in enumerate(pages, start=1) if len(t.strip()) < MIN_CHARS_PER_PAGE]
    empty = [n for n, t in enumerate(pages, start=1) if len(t.strip()) < EMPTY_PAGE_CHARS]
    total = sum(len(t.strip()) for t in pages)
    index = build_index(pages)
    index_path = dst.with_name("indice.txt")
    index_path.write_text("\n".join(index) + ("\n" if index else ""), encoding="utf-8")
    summary = {
        "metodo": method,
        "paginas": len(pages),
        "caracteres": total,
        "paginas_con_poco_texto": low,
        "paginas_sin_texto": empty,
        "entradas_indice": len(index),
        "indice": str(index_path),
        "salida": str(dst),
    }
    if inicios:
        summary["documentos"] = [{"archivo": documentos[0].name, "desde_pagina": 1}] + [
            {"archivo": nombre, "desde_pagina": n} for n, nombre in inicios.items()]
    tables = pages_maybe_tables(pages)
    if tables:
        summary["paginas_posible_tabla_o_columnas"] = tables  # leer con cautela; probar --layout
    if low and not args.sin_imagenes:
        imgs, error = dump_images([(n, *origenes[n - 1]) for n in low], dst.parent / "imagenes")
        if imgs:
            summary["imagenes"] = {str(n): paths for n, paths in imgs.items()}
            summary["lectura_visual_sugerida"] = (
                "Las páginas con poco texto contienen imágenes: abrirlas con una herramienta de visión y registrar lo que "
                "se lea con origen 'anexo-visual' (no se puede citar literalmente).")
        if error:
            summary["imagenes_error"] = error
    if low:
        summary["ocr_sugerido"] = f'ocrmypdf --skip-text "{src}" "{src.with_name(src.stem + "-ocr.pdf")}"'  # solo rehace páginas sin texto
    scanned = not pages or len(low) == len(pages)
    summary["posible_escaneado"] = scanned
    print(json.dumps(summary, ensure_ascii=False))
    return 2 if scanned else 0


if __name__ == "__main__":
    sys.exit(main())
