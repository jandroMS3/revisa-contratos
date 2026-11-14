#!/usr/bin/env python3
"""Compara dos revisiones de un mismo contrato y resume qué ha cambiado.

Uso:
  comparar_versiones.py informes/.trabajo/<slug-anterior> informes/.trabajo/<slug-nuevo> [--salida cambios.md]
  comparar_versiones.py <anterior> <nuevo> --paginas     # solo JSON con las páginas cambiadas del texto

Cada carpeta contiene texto.txt, riesgos.json, veredicto.json y resumen.json (los que falten se omiten).
Los riesgos se emparejan por similitud de cita/título porque los ids pueden renumerarse entre versiones.
Salida: Markdown por stdout (y a --salida si se indica). Código 0 correcto; 1 error de entrada.
"""
import argparse
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path

SEVERIDADES = ["critico", "alto", "medio", "bajo"]
UMBRAL = 0.6


def norm(s) -> str:
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", s)).strip()


def cargar(carpeta: Path, nombre: str):
    p = carpeta / nombre
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def similitud(a: dict, b: dict) -> float:
    ratio = lambda x, y: difflib.SequenceMatcher(None, norm(x), norm(y)).ratio() if x and y else 0.0
    return max(ratio(a.get("cita"), b.get("cita")), ratio(a.get("titulo"), b.get("titulo")))


def emparejar(antiguos, nuevos):
    candidatos = sorted(
        ((similitud(a, n), i, j) for i, a in enumerate(antiguos) for j, n in enumerate(nuevos)), reverse=True)
    usados_a, usados_n, pares = set(), set(), []
    for score, i, j in candidatos:
        if score < UMBRAL:
            break
        if i in usados_a or j in usados_n:
            continue
        usados_a.add(i)
        usados_n.add(j)
        pares.append((antiguos[i], nuevos[j]))
    sin_pareja_a = [a for i, a in enumerate(antiguos) if i not in usados_a]
    sin_pareja_n = [n for j, n in enumerate(nuevos) if j not in usados_n]
    return pares, sin_pareja_a, sin_pareja_n


def etiqueta(r) -> str:
    return f'{r.get("id")} · {r.get("titulo")} [{r.get("severidad")}]'


def cambios_texto(ant: Path, nue: Path):
    a, b = ant / "texto.txt", nue / "texto.txt"
    if not (a.exists() and b.exists()):
        return None
    la, lb = a.read_text(encoding="utf-8").splitlines(), b.read_text(encoding="utf-8").splitlines()
    if la == lb:
        return 0, 0
    sm = difflib.SequenceMatcher(None, la, lb, autojunk=False)
    quitadas = añadidas = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            quitadas += i2 - i1
            añadidas += j2 - j1
    return quitadas, añadidas


def paginas_de(path: Path):
    partes = re.split(r"=== Página (\d+) ===", path.read_text(encoding="utf-8"))
    return {int(partes[i]): norm(partes[i + 1]) for i in range(1, len(partes) - 1, 2)}


def paginas_cambiadas(ant: Path, nue: Path):
    """Páginas (de la versión nueva) cuyo texto difiere de la misma página anterior, y las que desaparecen/aparecen."""
    a, b = ant / "texto.txt", nue / "texto.txt"
    if not (a.exists() and b.exists()):
        return None
    pa, pb = paginas_de(a), paginas_de(b)
    return {
        "modificadas": sorted(n for n in pb if n in pa and pa[n] != pb[n]),
        "nuevas": sorted(n for n in pb if n not in pa),
        "eliminadas": sorted(n for n in pa if n not in pb),
    }


def comparar(ant: Path, nue: Path) -> str:
    out = [f"# Cambios entre `{ant.name}` y `{nue.name}`", ""]

    t = cambios_texto(ant, nue)
    out.append("## Texto del contrato")
    if t is None:
        out.append("No se puede comparar (falta texto.txt en alguna carpeta).")
    elif t == (0, 0):
        out.append("El texto extraído es idéntico: las diferencias vienen del análisis, no del contrato.")
    else:
        out.append(f"El contrato cambió: {t[0]} líneas eliminadas y {t[1]} añadidas. Revisar qué cláusulas se tocaron.")
        pc = paginas_cambiadas(ant, nue)
        if pc and any(pc.values()):
            for rotulo, paginas in (("Páginas modificadas", pc["modificadas"]), ("Páginas nuevas", pc["nuevas"]), ("Páginas eliminadas", pc["eliminadas"])):
                if paginas:
                    out.append(f"- {rotulo}: {', '.join(map(str, paginas))}")
    out.append("")

    va, vn = cargar(ant, "veredicto.json").get("veredicto", {}), cargar(nue, "veredicto.json").get("veredicto", {})
    out.append("## Veredicto")
    if va.get("nivel") == vn.get("nivel"):
        out.append(f"Sin cambio de nivel ({vn.get('nivel', '—')}).")
    else:
        out.append(f"Nivel: {va.get('nivel', '—')} → {vn.get('nivel', '—')}.")
    out.append("")

    ra, rn = cargar(ant, "riesgos.json").get("riesgos", []), cargar(nue, "riesgos.json").get("riesgos", [])
    pares, solo_ant, solo_nue = emparejar(ra, rn)
    out.append(f"## Riesgos ({len(ra)} → {len(rn)})")
    sube = [(a, n) for a, n in pares if SEVERIDADES.index(n["severidad"]) < SEVERIDADES.index(a["severidad"])]
    baja = [(a, n) for a, n in pares if SEVERIDADES.index(n["severidad"]) > SEVERIDADES.index(a["severidad"])]
    for titulo, lista, fmt in (
        ("Nuevos", solo_nue, lambda r: f"- {etiqueta(r)}"),
        ("Ya no aparecen (eliminados o fusionados)", solo_ant, lambda r: f"- {etiqueta(r)}"),
        ("Severidad aumentada", sube, lambda p: f"- {p[1].get('titulo')}: {p[0]['severidad']} → {p[1]['severidad']}"),
        ("Severidad reducida", baja, lambda p: f"- {p[1].get('titulo')}: {p[0]['severidad']} → {p[1]['severidad']}"),
    ):
        if lista:
            out += [f"### {titulo}", *map(fmt, lista), ""]
    if not (solo_nue or solo_ant or sube or baja):
        out += ["Sin diferencias de fondo.", ""]

    da = {norm(x.get("concepto")): x for x in cargar(ant, "resumen.json").get("datos_clave", [])}
    dn = {norm(x.get("concepto")): x for x in cargar(nue, "resumen.json").get("datos_clave", [])}
    nuevos_datos = [dn[k] for k in dn if k not in da]
    modificados = [(da[k], dn[k]) for k in dn if k in da and norm(da[k].get("valor")) != norm(dn[k].get("valor"))]
    if nuevos_datos or modificados:
        out.append("## Datos clave")
        out += [f"- Nuevo: {x['concepto']}: {x.get('valor')}" for x in nuevos_datos]
        out += [f"- Modificado: {n['concepto']}: «{a.get('valor')}» → «{n.get('valor')}»" for a, n in modificados]
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("anterior")
    ap.add_argument("nuevo")
    ap.add_argument("--salida")
    ap.add_argument("--paginas", action="store_true", help="imprime solo las páginas cambiadas (JSON)")
    args = ap.parse_args()
    ant, nue = Path(args.anterior), Path(args.nuevo)
    for p in (ant, nue):
        if not p.is_dir():
            print(f"ERROR: no existe la carpeta {p}", file=sys.stderr)
            return 1
    if args.paginas:
        print(json.dumps(paginas_cambiadas(ant, nue)))
        return 0
    md = comparar(ant, nue)
    if args.salida:
        Path(args.salida).write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
