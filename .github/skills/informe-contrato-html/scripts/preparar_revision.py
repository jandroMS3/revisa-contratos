#!/usr/bin/env python3
"""Calcula de forma determinista el slug, la versión y las carpetas de una revisión de contrato.

Uso:
  preparar_revision.py "contratos/Alquiler Piso.pdf" [--no-crear] [--forzar-nueva]

Reglas:
  - base = nombre del PDF sin extensión, sin acentos, en minúsculas y con todo lo no alfanumérico como '-'.
  - Sin revisiones previas: slug = base. Con previas: slug = base-v<N+1> (la primera no lleva sufijo).
  - Si la última carpeta de trabajo quedó sin informe (ejecución interrumpida) se reutiliza, salvo --forzar-nueva.
  - Guarda el SHA-256 del PDF en <carpeta>/.pdf.sha256 y lo compara con el de la versión anterior.
Salida: JSON por stdout. Código 0 correcto; 1 error de entrada.
"""
import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path.cwd()


def slugify(nombre: str) -> str:
    s = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "contrato"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def version_de(slug: str, base: str):
    if slug == base:
        return 1
    m = re.fullmatch(re.escape(base) + r"-v(\d+)", slug)
    return int(m.group(1)) if m else None


def slug_de(base: str, version: int) -> str:
    return base if version == 1 else f"{base}-v{version}"


def versiones_existentes(base: str, informes: Path):
    """{versión: {'informe': bool, 'trabajo': bool}} a partir de los HTML y de las carpetas de trabajo."""
    encontradas = {}
    for p in informes.glob("*-informe.html"):
        v = version_de(p.name[: -len("-informe.html")], base)
        if v:
            encontradas.setdefault(v, {"informe": False, "trabajo": False})["informe"] = True
    trabajo = informes / ".trabajo"
    if trabajo.is_dir():
        for p in trabajo.iterdir():
            v = version_de(p.name, base) if p.is_dir() else None
            if v:
                encontradas.setdefault(v, {"informe": False, "trabajo": False})["trabajo"] = True
    return dict(sorted(encontradas.items()))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--no-crear", action="store_true", help="no crea la carpeta de trabajo")
    ap.add_argument("--forzar-nueva", action="store_true", help="crea una versión nueva aunque la última esté incompleta")
    ap.add_argument("--informes", default="informes", help="carpeta de informes (por defecto 'informes')")
    args = ap.parse_args()

    pdf = Path(args.pdf)
    if not pdf.is_file():
        print(f"ERROR: no existe el PDF {pdf}", file=sys.stderr)
        return 1
    informes = Path(args.informes)
    base = slugify(pdf.stem)
    existentes = versiones_existentes(base, informes)

    reutiliza = False
    if not existentes:
        version, anterior = 1, None
    else:
        ultima = max(existentes)
        estado = existentes[ultima]
        if estado["trabajo"] and not estado["informe"] and not args.forzar_nueva:
            version, reutiliza = ultima, True
            previas = [v for v in existentes if v < ultima and existentes[v]["informe"]]
            anterior = slug_de(base, max(previas)) if previas else None
        else:
            version = ultima + 1
            completas = [v for v in existentes if existentes[v]["informe"]]
            anterior = slug_de(base, max(completas)) if completas else None
    slug = slug_de(base, version)
    carpeta = informes / ".trabajo" / slug

    huella = sha256(pdf)
    huella_anterior = None
    if anterior:
        f = informes / ".trabajo" / anterior / ".pdf.sha256"
        huella_anterior = f.read_text(encoding="utf-8").strip() if f.exists() else None
    if not args.no_crear:
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / ".pdf.sha256").write_text(huella + "\n", encoding="utf-8")

    print(json.dumps({
        "pdf": str(pdf),
        "base": base,
        "slug": slug,
        "version": version,
        "reutiliza_carpeta_incompleta": reutiliza,
        "version_anterior": anterior,
        "carpeta_anterior": str(informes / ".trabajo" / anterior) if anterior else None,
        "carpeta_trabajo": str(carpeta),
        "informe": str(informes / f"{slug}-informe.html"),
        "cambios": str(informes / f"{slug}-cambios.md") if anterior else None,
        "pdf_sha256": huella,
        "pdf_cambiado": None if huella_anterior is None else huella != huella_anterior,
        "versiones_existentes": {slug_de(base, v): e for v, e in existentes.items()},
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
