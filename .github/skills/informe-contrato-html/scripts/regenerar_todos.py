#!/usr/bin/env python3
"""Regenera los informes HTML a partir de los fragmentos ya existentes (p. ej. tras cambiar el diseño).

Uso:
  regenerar_todos.py [--informes informes] [--solo slug ...] [--anonimizar]

Recorre informes/.trabajo/<slug>/ con los cinco fragmentos (meta, resumen, riesgos, mejoras, veredicto)
y renderiza informes/<slug>-informe.html con render_report.py. No relanza ningún agente.
Salida: 0 todo correcto; 3 algún informe con avisos de calidad (se genera igualmente); 1 algún error.
"""
import argparse
import subprocess
import sys
from pathlib import Path

FRAGMENTOS = ["meta", "resumen", "riesgos", "mejoras", "veredicto"]
RENDER = Path(__file__).resolve().parent / "render_report.py"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--informes", default="informes")
    ap.add_argument("--solo", nargs="*", help="limitar a estos slugs")
    ap.add_argument("--anonimizar", action="store_true", help="enmascara DNI/NIE/IBAN en los HTML")
    args = ap.parse_args()

    informes = Path(args.informes)
    carpetas = sorted(p for p in (informes / ".trabajo").glob("*") if p.is_dir())
    if args.solo:
        carpetas = [p for p in carpetas if p.name in args.solo]
    if not carpetas:
        print("No hay carpetas de trabajo que regenerar.", file=sys.stderr)
        return 1

    peor = 0
    for carpeta in carpetas:
        fragmentos = [carpeta / f"{n}.json" for n in FRAGMENTOS]
        if not all(f.exists() for f in fragmentos):
            print(f"- {carpeta.name}: omitido (faltan fragmentos: {', '.join(f.stem for f in fragmentos if not f.exists())})")
            continue
        cmd = [sys.executable, str(RENDER), "--salida", str(informes / f"{carpeta.name}-informe.html")]
        if (carpeta / "texto.txt").exists():
            cmd += ["--texto", str(carpeta / "texto.txt")]
        if args.anonimizar:
            cmd.append("--anonimizar")
        proc = subprocess.run(cmd + [str(f) for f in fragmentos], capture_output=True, text=True)
        estado = {0: "correcto", 3: "generado con avisos"}.get(proc.returncode, "ERROR")
        print(f"- {carpeta.name}: {estado}")
        if proc.returncode:
            print("  " + proc.stderr.strip().replace("\n", "\n  "))
        if proc.returncode == 1 or (proc.returncode == 3 and peor != 1):
            peor = proc.returncode
    return peor


if __name__ == "__main__":
    sys.exit(main())
