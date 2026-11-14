#!/usr/bin/env python3
"""Comprueba que una revisión solo ha tocado sus propios ficheros (sustituye al frágil `find -newer`).

Uso:
  integridad.py guardar  <slug>     # antes de delegar: guarda el hash de todos los ficheros del proyecto
  integridad.py comprobar <slug>    # después: lista lo modificado, nuevo o eliminado fuera de lo permitido

Permitido para un slug: informes/.trabajo/<slug>/**, informes/<slug>-informe.html e informes/<slug>-cambios.md.
Se ignoran .venv, .git, __pycache__, node_modules y .DS_Store. Las carpetas de versiones anteriores
(informes/.trabajo/<otro-slug>/) SÍ se vigilan: una revisión nueva no debe alterarlas.
Salida: JSON por stdout. Código 0 correcto; 1 hay cambios no permitidos o falta la instantánea.
"""
import hashlib
import json
import sys
from pathlib import Path

IGNORAR_DIRS = {".venv", ".git", "__pycache__", "node_modules"}
IGNORAR_FICHEROS = {".DS_Store"}


def huella(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def instantanea(raiz: Path):
    estado = {}
    for p in raiz.rglob("*"):
        rel = p.relative_to(raiz)
        if not p.is_file() or p.name in IGNORAR_FICHEROS or IGNORAR_DIRS & set(rel.parts):
            continue
        estado[rel.as_posix()] = huella(p)
    return estado


def permitido(rel: str, slug: str) -> bool:
    return (rel.startswith(f"informes/.trabajo/{slug}/")
            or rel in (f"informes/{slug}-informe.html", f"informes/{slug}-cambios.md"))


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in ("guardar", "comprobar"):
        print(__doc__, file=sys.stderr)
        return 1
    accion, slug = sys.argv[1], sys.argv[2]
    raiz = Path.cwd()
    destino = raiz / "informes" / ".trabajo" / slug / ".integridad.json"
    if accion == "guardar":
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(instantanea(raiz), indent=0), encoding="utf-8")
        print(json.dumps({"ok": True, "guardados": len(json.loads(destino.read_text(encoding="utf-8")))}))
        return 0
    if not destino.exists():
        print(json.dumps({"ok": False, "error": "no hay instantánea; ejecuta primero 'guardar'"}))
        return 1
    antes, ahora = json.loads(destino.read_text(encoding="utf-8")), instantanea(raiz)
    modificados = sorted(r for r in antes if r in ahora and antes[r] != ahora[r] and not permitido(r, slug))
    nuevos = sorted(r for r in ahora if r not in antes and not permitido(r, slug))
    eliminados = sorted(r for r in antes if r not in ahora and not permitido(r, slug))
    ok = not (modificados or nuevos or eliminados)
    print(json.dumps({"ok": ok, "modificados": modificados, "nuevos": nuevos, "eliminados": eliminados}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
