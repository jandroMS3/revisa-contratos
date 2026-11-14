#!/usr/bin/env python3
"""Genera el informe HTML de revisión de contrato a partir de fragmentos JSON.

Uso:
  render_report.py --texto texto.txt --salida informe.html frag1.json [frag2.json ...]
  render_report.py --texto texto.txt --validar frag1.json [frag2.json ...]   (solo comprueba, no genera HTML)
  render_report.py --texto texto.txt --fragmento riesgos riesgos.json        (valida solo un fragmento de un especialista)
  render_report.py --fragmento mejoras --texto texto.txt mejoras.json riesgos.json   (con riesgos.json también valida referencias y cobertura)

Los fragmentos se fusionan por clave de primer nivel (los posteriores pisan a los anteriores).
Esquema: .github/skills/informe-contrato-html/references/esquema-json.md
Salida: 0 correcto; 1 error de entrada/validación (no se genera HTML);
        3 avisos de calidad (citas no verificadas, cortas o en otra página, riesgos medio+ sin mejora,
          veredicto inferior al riesgo máximo o con recuentos que no cuadran...). El HTML se genera igualmente
          salvo con --validar/--fragmento; usar --permisivo para tratar los avisos como no bloqueantes (salida 0).
Opciones de salida: --anonimizar enmascara DNI/NIE e IBAN en el HTML.
"""
import argparse
import html
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

SEVERIDADES = ["critico", "alto", "medio", "bajo"]
PRIORIDADES = ["alta", "media", "baja"]
ORIGENES = ["texto", "anexo-visual"]
ETIQUETA_SEV = {"critico": "Crítico", "alto": "Alto", "medio": "Medio", "bajo": "Bajo"}
ETIQUETA_PRI = {"alta": "Alta", "media": "Media", "baja": "Baja"}
OBLIGATORIOS = ["titulo", "rol_usuario", "resumen", "riesgos", "mejoras", "veredicto"]
CITA_MIN = 40  # caracteres normalizados; por debajo la cita no demuestra nada
CITA_EXTRA_MIN = 25  # citas adicionales (`citas`) de riesgos que fusionan varias cláusulas
CITA_MAX = 300
MAX_RIESGOS = 20
TOP_PRIORIDADES = 5
# Secciones con filas que pueden llevar una `cita` opcional verificable contra el texto
SECCIONES_CON_CITA = ("datos_clave", "puntos_clave", "fechas_plazos", "clausulas_ausentes")
FRAGMENTOS = ("resumen", "riesgos", "mejoras")
ASSETS = Path(__file__).resolve().parent.parent / "assets"

AVISO = (
    "Este informe es un análisis automatizado de apoyo y no constituye asesoramiento jurídico. "
    "Las citas proceden del texto extraído del PDF y pueden contener errores de extracción. "
    "Antes de firmar, consulte con un abogado, especialmente si se trata de un contrato de alto valor o con riesgos críticos."
)


class Raw(str):
    """HTML ya escapado que `esc` no debe volver a escapar."""


# ---------------------------------------------------------------- anonimizado
_ANONIMIZAR = False
_PERSONALES = [
    (re.compile(r"\bES\d{2}(?:\s?\d{4}){5}\b"), lambda t: t[:4] + " **** **** **** **** " + t[-4:]),
    (re.compile(r"\b[XYZxyz]?\d{7,8}-?[A-Za-z]\b"), lambda t: "*" * (len(t) - 3) + t[-3:]),
    (re.compile(r"\b\d{2}\.\d{3}\.\d{3}[-\s]?[A-Za-z]\b"), lambda t: "**.***.*" + t[-4:]),
]


def mask(s: str) -> str:
    if _ANONIMIZAR:
        for patron, fn in _PERSONALES:
            s = patron.sub(lambda m, fn=fn: fn(m.group(0)), s)
    return s


def esc(x) -> str:
    if isinstance(x, Raw):
        return x
    return html.escape(mask("" if x is None else str(x))).replace("\n", "<br>")


def paragraphs(text) -> str:
    parts = [p.strip() for p in str(text or "").split("\n\n") if p.strip()]
    return "".join(f"<p>{esc(p)}</p>" for p in parts)


def norm_key(value, allowed, default):
    s = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower().strip()
    return s if s in allowed else default


def norm_text(s: str) -> str:
    s = re.sub(r"-\s*\n\s*", "", s)
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"[\u2018\u2019\u201c\u201d\"'«»]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def li(items) -> str:
    return "<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>" if items else ""


def table(headers, rows) -> str:
    if not rows:
        return ""
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f'<td data-label="{html.escape(h)}">{esc(c)}</td>' for h, c in zip(headers, r)) + "</tr>"
        for r in rows)
    return f'<div class="tabla"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def quote(cita) -> str:
    return f"<blockquote>{esc(cita)}</blockquote>" if cita else ""


def dl(pairs) -> str:
    rows = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in pairs if v)
    return f"<dl>{rows}</dl>" if rows else ""


def con_origen(valor, fila):
    """Marca visualmente los datos leídos de anexos en imagen (no verificables con cita literal)."""
    if norm_key(fila.get("origen"), ORIGENES, "texto") == "anexo-visual":
        return Raw(f'{esc(valor)} <span class="tag">Leído de imagen · sin verificar</span>')
    return valor


def load(paths):
    data = {}
    for p in paths:
        try:
            frag = json.loads(Path(p).read_text(encoding="utf-8"))
        except FileNotFoundError:
            sys.exit(f"Error: no existe {p}")
        except json.JSONDecodeError as exc:
            sys.exit(f"Error: JSON inválido en {p} (línea {exc.lineno}, col {exc.colno}): {exc.msg}")
        if not isinstance(frag, dict):
            sys.exit(f"Error: {p} debe contener un objeto JSON")
        data.update(frag)
    return data


def strict_key(value, allowed):
    """Devuelve la clave normalizada o None si no es un valor permitido (sin degradar en silencio)."""
    return norm_key(value, allowed, None)


def related_ids(value):
    """`riesgo_relacionado` admite un id, una lista de ids o 'R1, R2'."""
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [p for p in re.split(r"[,;\s]+", str(value or "")) if p]


# ----------------------------------------------------------------- validación
def _errores_riesgos(riesgos):
    errores, ids = [], []
    for n, r in enumerate(riesgos, start=1):
        if not isinstance(r, dict):
            errores.append(f"riesgos[{n}] debe ser un objeto")
            continue
        rid = str(r.get("id") or "").strip()
        if not rid:
            errores.append(f"riesgos[{n}] ('{str(r.get('titulo', ''))[:40]}') no tiene 'id'")
        ids.append(rid)
        if strict_key(r.get("severidad"), SEVERIDADES) is None:
            errores.append(f"riesgo {rid or n}: severidad '{r.get('severidad')}' no válida ({'|'.join(SEVERIDADES)})")
        if r.get("origen") is not None and strict_key(r.get("origen"), ORIGENES) is None:
            errores.append(f"riesgo {rid or n}: origen '{r.get('origen')}' no válido ({'|'.join(ORIGENES)})")
        if r.get("citas") is not None and not isinstance(r["citas"], list):
            errores.append(f"riesgo {rid or n}: 'citas' debe ser una lista de textos")
    errores += [f"id de riesgo duplicado: {rid}" for rid in sorted({i for i in ids if i and ids.count(i) > 1})]
    return errores, ids


def _errores_mejoras(mejoras, ids):
    errores = []
    for n, m in enumerate(mejoras, start=1):
        if not isinstance(m, dict):
            errores.append(f"mejoras[{n}] debe ser un objeto")
            continue
        if strict_key(m.get("prioridad"), PRIORIDADES) is None:
            errores.append(f"mejora {n} ('{str(m.get('titulo'))[:40]}'): prioridad '{m.get('prioridad')}' no válida ({'|'.join(PRIORIDADES)})")
        if ids is not None:
            for ref in related_ids(m.get("riesgo_relacionado")):
                if ref not in ids:
                    errores.append(f"mejora {n} ('{str(m.get('titulo'))[:40]}'): riesgo_relacionado '{ref}' no existe")
    return errores


def validate(d):
    """Errores bloqueantes: estructura, enums, ids duplicados y referencias rotas."""
    errores = [f"falta el campo obligatorio '{k}'" for k in OBLIGATORIOS if not d.get(k)]
    for key in ("riesgos", "mejoras"):
        if d.get(key) and not isinstance(d[key], list):
            errores.append(f"'{key}' debe ser una lista")
    if d.get("veredicto") and not isinstance(d["veredicto"], dict):
        errores.append("'veredicto' debe ser un objeto")
    if errores:
        return errores

    errores, ids = _errores_riesgos(d["riesgos"])
    errores += _errores_mejoras(d["mejoras"], ids)
    v = d["veredicto"]
    if strict_key(v.get("nivel"), SEVERIDADES) is None:
        errores.append(f"veredicto.nivel '{v.get('nivel')}' no válido ({'|'.join(SEVERIDADES)})")
    for ref in related_ids(v.get("prioridades")):
        if ref not in ids:
            errores.append(f"veredicto.prioridades: el riesgo '{ref}' no existe")
    return errores


def validate_fragmento(d, tipo):
    """Valida un único fragmento de especialista (sin exigir el resto del informe)."""
    errores = []
    if tipo == "resumen":
        if not d.get("resumen"):
            errores.append("falta el campo obligatorio 'resumen'")
        for seccion in ("partes", "datos_clave", "puntos_clave", "fechas_plazos"):
            if d.get(seccion) is not None and not (isinstance(d[seccion], list) and all(isinstance(x, dict) for x in d[seccion])):
                errores.append(f"'{seccion}' debe ser una lista de objetos")
    elif tipo == "riesgos":
        if not isinstance(d.get("riesgos"), list) or not d["riesgos"]:
            errores.append("falta la lista obligatoria 'riesgos'")
        else:
            errores += _errores_riesgos(d["riesgos"])[0]
    elif tipo == "mejoras":
        if not isinstance(d.get("mejoras"), list) or not d["mejoras"]:
            errores.append("falta la lista obligatoria 'mejoras'")
        else:
            ids = _errores_riesgos(d["riesgos"])[1] if isinstance(d.get("riesgos"), list) else None
            errores += _errores_mejoras(d["mejoras"], ids)
    return errores


# -------------------------------------------------------------------- citas
def split_cita(cita):
    return [s for s in re.split(r"\.\.\.|…|\[\.\.\.\]", cita) if s.strip()]


def check_cita(cita, corpus, minimo=CITA_MIN):
    """Devuelve un motivo de aviso o None si la cita es válida y aparece en el texto."""
    cita = str(cita or "").strip()
    if len(cita) > CITA_MAX:
        return f"cita de {len(cita)} caracteres (máx. {CITA_MAX})"
    segmentos = split_cita(cita)
    if sum(len(norm_text(s)) for s in segmentos) < minimo:
        return f"cita demasiado corta (<{minimo} caracteres): no demuestra nada"
    if corpus is not None and any(norm_text(s) not in corpus for s in segmentos if len(norm_text(s)) >= 12):
        return "cita no encontrada en el texto del contrato"
    return None


def read_pages(texto_path):
    """Devuelve {n_página: texto normalizado} a partir de los marcadores `=== Página N ===`."""
    raw = Path(texto_path).read_text(encoding="utf-8")
    partes = re.split(r"=== Página (\d+) ===", raw)
    if len(partes) < 3:
        return {1: norm_text(raw)}
    return {int(partes[i]): norm_text(partes[i + 1]) for i in range(1, len(partes) - 1, 2)}


def paginas_indicadas(clausula):
    """Páginas mencionadas en un texto como 'Cláusula 2.7 (pág. 6)' o 'págs. 9-11, 14'."""
    paginas = set()
    for m in re.finditer(r"p[áa]gs?\.?\s*((?:\d+(?:\s*[-–]\s*\d+)?\s*(?:,|\by\b|\be\b)?\s*)+)", str(clausula or ""), re.I):
        for a, b in re.findall(r"(\d+)(?:\s*[-–]\s*(\d+))?", m.group(1)):
            paginas.update(range(int(a), int(b or a) + 1))
    return paginas


def aviso_pagina(cita, clausula, paginas):
    """Avisa si la cita está en una página que la cláusula no menciona (±1 por saltos de página)."""
    indicadas = paginas_indicadas(clausula)
    if not paginas or not indicadas:
        return None
    encontradas = {n for n, t in paginas.items() for s in split_cita(str(cita or "")) if len(norm_text(s)) >= 12 and norm_text(s) in t}
    if not encontradas:
        return None  # cita repartida entre páginas o no encontrada (otro aviso)
    if any(abs(e - i) <= 1 for e in encontradas for i in indicadas):
        return None
    return f"la cita está en pág. {', '.join(map(str, sorted(encontradas)))} pero la cláusula indica pág. {', '.join(map(str, sorted(indicadas)))}"


def _citas_de(r):
    """Cita principal más las adicionales de un riesgo que fusiona varias cláusulas."""
    yield r.get("cita"), CITA_MIN
    for extra in r.get("citas") or []:
        yield extra, CITA_EXTRA_MIN


def avisos_citas(d, corpus, paginas):
    avisos = []
    for r in d.get("riesgos") or []:
        if not isinstance(r, dict) or norm_key(r.get("origen"), ORIGENES, "texto") == "anexo-visual":
            continue
        etiqueta = f"{r.get('id')} {str(r.get('titulo', ''))[:60]}"
        if not str(r.get("cita") or "").strip():
            avisos.append(f"{etiqueta}: riesgo sin cita literal (si no se puede citar, es una ausencia o una duda; "
                          "si viene de un anexo en imagen, usar origen 'anexo-visual')")
        for cita, minimo in _citas_de(r):
            if not str(cita or "").strip():
                continue
            if (motivo := check_cita(cita, corpus, minimo)):
                avisos.append(f"{etiqueta}: {motivo} «{str(cita)[:80]}»")
            elif (motivo := aviso_pagina(cita, r.get("clausula"), paginas)):
                avisos.append(f"{etiqueta}: {motivo}")

    for seccion in SECCIONES_CON_CITA:
        for fila in d.get(seccion) or []:
            if not isinstance(fila, dict) or not str(fila.get("cita") or "").strip():
                continue
            if norm_key(fila.get("origen"), ORIGENES, "texto") == "anexo-visual":
                continue
            nombre = str(fila.get("titulo") or fila.get("concepto") or "?")[:50]
            if (motivo := check_cita(fila["cita"], corpus)):
                avisos.append(f"{seccion} '{nombre}': {motivo}")
            elif (motivo := aviso_pagina(fila["cita"], fila.get("clausula"), paginas)):
                avisos.append(f"{seccion} '{nombre}': {motivo}")
    return avisos


def avisos_cobertura(d):
    cubiertos = {ref for m in d.get("mejoras") or [] if isinstance(m, dict) for ref in related_ids(m.get("riesgo_relacionado"))}
    sin_mejora = [r["id"] for r in d.get("riesgos") or []
                  if strict_key(r.get("severidad"), SEVERIDADES) in ("critico", "alto", "medio") and r["id"] not in cubiertos]
    return ["riesgos medio o superior sin mejora asociada: " + ", ".join(sin_mejora)] if sin_mejora else []


_RECUENTO = re.compile(r"(\d+)\s+(?:riesgos?\s+)?(cr[ií]tic[oa]s?|alt[oa]s?|medi[oa]s?|baj[oa]s?)\b", re.I)
_NIVEL_PREFIJO = {"cr": "critico", "al": "alto", "me": "medio", "ba": "bajo"}


def avisos_veredicto(d):
    avisos = []
    max_sev = min((SEVERIDADES.index(strict_key(r["severidad"], SEVERIDADES)) for r in d["riesgos"]), default=None)
    nivel = SEVERIDADES.index(strict_key(d["veredicto"]["nivel"], SEVERIDADES))
    if max_sev is not None and nivel > max_sev:
        avisos.append(f"el veredicto ('{SEVERIDADES[nivel]}') es inferior al riesgo más alto detectado ('{SEVERIDADES[max_sev]}')")
    reales = {s: sum(1 for r in d["riesgos"] if strict_key(r.get("severidad"), SEVERIDADES) == s) for s in SEVERIDADES}
    for n, etiqueta in _RECUENTO.findall(str(d["veredicto"].get("texto") or "")):
        sev = _NIVEL_PREFIJO[etiqueta[:2].lower()]
        if int(n) != reales[sev]:
            avisos.append(f"veredicto.texto dice «{n} {etiqueta}» pero hay {reales[sev]} riesgos de nivel {sev} "
                          "(no escribas recuentos a mano: los calcula el renderizador)")
    return avisos


def quality(d, texto_path, fragmento=None):
    """Avisos de calidad (exit 3): citas, páginas, cobertura de mejoras, coherencia del veredicto, exceso de riesgos."""
    avisos = []
    corpus = paginas = None
    if texto_path:
        paginas = read_pages(texto_path)
        corpus = " ".join(paginas.values())
    else:
        avisos.append("no se indicó --texto: las citas NO se han verificado contra el contrato")

    avisos += avisos_citas(d, corpus, paginas)
    if fragmento in (None, "mejoras") and d.get("riesgos") and d.get("mejoras"):
        avisos += avisos_cobertura(d)
    if fragmento is None:
        avisos += avisos_veredicto(d)
        if len(d["riesgos"]) > MAX_RIESGOS:
            avisos.append(f"{len(d['riesgos'])} riesgos (> {MAX_RIESGOS}): fusionar solapamientos y agrupar por tema")
        if not d.get("fecha_analisis"):
            avisos.append("falta 'fecha_analisis' en meta.json: al regenerar el informe se pondría la fecha de ese día")
    return avisos


# --------------------------------------------------------------------- render
def tarjeta(id_, clases, sev_attr, resumen_html, cuerpo_html, abierta):
    return (f'<details id="{id_}" class="card {clases}" {sev_attr}{" open" if abierta else ""}>'
            f'<summary>{resumen_html}</summary><div class="cuerpo">{cuerpo_html}</div></details>')


def render(d) -> str:
    nivel = norm_key(d["veredicto"].get("nivel"), SEVERIDADES, "medio")
    riesgos = sorted(d["riesgos"], key=lambda r: SEVERIDADES.index(norm_key(r.get("severidad"), SEVERIDADES, "medio")))
    mejoras = sorted(d["mejoras"], key=lambda m: PRIORIDADES.index(norm_key(m.get("prioridad"), PRIORIDADES, "media")))
    ids_mejora = {id(m): f"M{n}" for n, m in enumerate(mejoras, start=1)}
    mejoras_de = {}
    for m in mejoras:
        for ref in related_ids(m.get("riesgo_relacionado")):
            mejoras_de.setdefault(ref, []).append(m)
    secciones = []

    def add(id_, titulo, body, cls=""):
        if body:
            secciones.append((id_, titulo, f'<section id="{id_}" class="{cls}"><h2>{esc(titulo)}</h2>{body}</section>'))

    v = d["veredicto"]
    cuenta = {s: sum(1 for r in riesgos if norm_key(r.get("severidad"), SEVERIDADES, "medio") == s) for s in SEVERIDADES}
    tiles = "".join(f'<div class="tile sev-{s}"><b>{n}</b><span>{ETIQUETA_SEV[s]}</span></div>' for s, n in cuenta.items())
    por_id = {str(r.get("id")): r for r in riesgos}
    elegidos = related_ids(v.get("prioridades")) or [str(r.get("id")) for r in riesgos[:TOP_PRIORIDADES]]
    top = "".join(
        f'<li><a href="#riesgo-{esc(i)}"><b>{esc(i)}</b> · {esc(por_id[i].get("titulo"))}</a> '
        f'<span class="badge sev-{norm_key(por_id[i].get("severidad"), SEVERIDADES, "medio")}">'
        f'{ETIQUETA_SEV[norm_key(por_id[i].get("severidad"), SEVERIDADES, "medio")]}</span></li>'
        for i in elegidos if i in por_id)
    top_html = f'<h3>Qué negociar primero</h3><ol class="prioridades">{top}</ol>' if top else ""
    add("veredicto", "Veredicto general",
        f'<div class="verdict sev-{nivel}"><span class="badge">Riesgo global: {ETIQUETA_SEV[nivel]}</span>'
        f'<div class="rec">{esc(v.get("recomendacion"))}</div>{paragraphs(v.get("texto"))}'
        f'<div class="conteo">{tiles}</div>{top_html}</div>')
    add("advertencias", "Advertencias sobre el análisis", li(d.get("advertencias")), "warn")

    add("resumen", "Resumen ejecutivo", paragraphs(d.get("resumen")))

    add("partes", "Partes", table(["Parte", "Rol", "Detalle"],
        [(p.get("nombre"), p.get("rol"), p.get("detalle")) for p in d.get("partes") or []]))

    add("datos", "Datos clave", table(["Concepto", "Valor", "Cláusula"],
        [(x.get("concepto"), con_origen(x.get("valor"), x), x.get("clausula")) for x in d.get("datos_clave") or []]))

    puntos = "".join(
        f'<article class="card"><header><h3>{esc(p.get("titulo"))}</h3>'
        f'<span class="clausula">{esc(p.get("clausula"))}</span></header>{paragraphs(p.get("descripcion"))}'
        f'{quote(p.get("cita"))}</article>'
        for p in d.get("puntos_clave") or [])
    add("puntos", "Puntos clave", puntos)

    add("fechas", "Fechas y plazos", table(["Concepto", "Fecha / plazo", "Cláusula"],
        [(x.get("concepto"), con_origen(x.get("fecha_o_plazo"), x), x.get("clausula")) for x in d.get("fechas_plazos") or []]))

    ob = d.get("obligaciones") or {}
    if ob.get("usuario") or ob.get("contraparte"):
        add("obligaciones", "Obligaciones",
            f'<div class="cols"><div><h3>Tus obligaciones ({esc(d["rol_usuario"])})</h3>{li(ob.get("usuario"))}</div>'
            f'<div><h3>Obligaciones de la contraparte</h3>{li(ob.get("contraparte"))}</div></div>')

    tarjetas = []
    for r in riesgos:
        s = norm_key(r.get("severidad"), SEVERIDADES, "medio")
        rid = esc(r.get("id"))
        citas = quote(r.get("cita")) + "".join(quote(c) for c in r.get("citas") or [])
        origen = ('<p><span class="tag">Leído de imagen · sin verificar</span></p>'
                  if norm_key(r.get("origen"), ORIGENES, "texto") == "anexo-visual" else "")
        enlaces = "".join(f'<a href="#mejora-{ids_mejora[id(m)]}">{ids_mejora[id(m)]} · {esc(m.get("titulo"))}</a>'
                          for m in mejoras_de.get(str(r.get("id")), []))
        enlaces_html = f'<div class="enlaces"><span>Mejoras propuestas</span>{enlaces}</div>' if enlaces else ""
        cuerpo = (f'{origen}{citas}'
                  f'{dl([("Qué dice y por qué es un riesgo", r.get("descripcion")), ("Impacto para ti", r.get("impacto")), ("Probabilidad", r.get("probabilidad")), ("Recomendación", r.get("recomendacion"))])}'
                  f'{enlaces_html}')
        resumen = (f'<span class="badge">{ETIQUETA_SEV[s]}</span><h3><span class="rid">{rid}</span> {esc(r.get("titulo"))}</h3>'
                   f'<span class="clausula">{esc(r.get("clausula"))}</span>')
        tarjetas.append(tarjeta(f"riesgo-{rid}", f"sev-{s}", f'data-sev="{s}"', resumen, cuerpo, s in ("critico", "alto")))
    filtros = ('<div class="filtros" role="group" aria-label="Filtrar riesgos por severidad">'
               '<button type="button" data-f="todos" aria-pressed="true">Todos</button>'
               + "".join(f'<button type="button" data-f="{s}" aria-pressed="false">{ETIQUETA_SEV[s]} ({n})</button>'
                         for s, n in cuenta.items() if n)
               + '<button type="button" class="plegar" data-plegar="riesgos">Abrir / cerrar todo</button></div>')
    add("riesgos", "Riesgos para ti", filtros + "".join(tarjetas))

    add("ausentes", "Cláusulas ausentes que te perjudican",
        "".join(f'<article class="card"><h3>{esc(c.get("titulo"))}</h3>{paragraphs(c.get("por_que_importa"))}</article>'
                for c in d.get("clausulas_ausentes") or []))

    tarjetas = []
    for m in mejoras:
        p = norm_key(m.get("prioridad"), PRIORIDADES, "media")
        mid = ids_mejora[id(m)]
        refs = "".join(f'<a href="#riesgo-{esc(i)}">{esc(i)}</a>' for i in related_ids(m.get("riesgo_relacionado")))
        red = ""
        if m.get("redaccion_sugerida"):
            red = (f'<dt>Redacción sugerida</dt><dd><div class="redaccion-wrap"><button type="button" class="copiar">Copiar</button>'
                   f'<div class="redaccion">{esc(m["redaccion_sugerida"])}</div></div></dd>')
        resumen = (f'<span class="badge pri-{p}">Prioridad {ETIQUETA_PRI[p]}</span>'
                   f'<h3><span class="rid">{mid}</span> {esc(m.get("titulo"))}</h3>'
                   f'<span class="clausula">{esc(m.get("clausula_afectada"))}</span>')
        cuerpo = (f'<div class="enlaces"><span>Responde a</span>{refs}</div>' if refs else "")
        cuerpo += (f'{dl([("Situación actual", m.get("situacion_actual")), ("Propuesta", m.get("propuesta"))])}'
                   f'<dl>{red}</dl>'
                   f'{dl([("Por qué te beneficia", m.get("justificacion")), ("Dificultad de negociación", m.get("dificultad_negociacion"))])}')
        tarjetas.append(tarjeta(f"mejora-{mid}", f"pri-{p}", "", resumen, cuerpo, p == "alta"))
    plegar = '<div class="filtros"><button type="button" class="plegar" data-plegar="mejoras">Abrir / cerrar todo</button></div>'
    add("mejoras", "Mejoras propuestas para ti", plegar + "".join(tarjetas))

    add("preguntas", "Preguntas abiertas antes de firmar", li(d.get("preguntas_abiertas")))

    meta = [("Archivo", d.get("archivo")), ("Tipo", d.get("tipo_contrato")), ("Tu rol", d.get("rol_usuario")),
            ("Jurisdicción", d.get("jurisdiccion") or "No indicada en el contrato"),
            ("Fecha del análisis", d.get("fecha_analisis") or date.today().isoformat())]
    meta_html = "".join(f"<span><b>{esc(k)}:</b> {esc(val)}</span>" for k, val in meta if val)
    toc = "".join(f'<a href="#{i}">{esc(t)}</a>' for i, t, _ in secciones)
    css = (ASSETS / "estilo.css").read_text(encoding="utf-8")
    js = (ASSETS / "informe.js").read_text(encoding="utf-8")
    return (
        '<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>Informe: {esc(d["titulo"])}</title><style>{css}</style></head><body><div class="wrap">'
        f'<header class="top"><button type="button" class="tema" aria-label="Cambiar entre tema claro y oscuro">◐</button>'
        f'<div class="eyebrow">Informe de revisión contractual</div><h1>{esc(d["titulo"])}</h1><div class="meta">{meta_html}</div></header>'
        f'<div class="layout"><nav class="toc" aria-label="Contenido"><div class="toc-title">Contenido</div>{toc}</nav>'
        f'<main>{"".join(s for _, _, s in secciones)}</main></div>'
        f'<footer>{esc(AVISO)}</footer></div><script>{js}</script></body></html>'
    )


def main() -> int:
    global _ANONIMIZAR
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fragmentos", nargs="+")
    ap.add_argument("--salida", help="ruta del HTML (obligatoria salvo con --validar/--fragmento)")
    ap.add_argument("--texto", help="texto extraído del contrato para verificar citas (muy recomendable)")
    ap.add_argument("--validar", action="store_true", help="solo valida y avisa; no genera el HTML")
    ap.add_argument("--fragmento", choices=FRAGMENTOS, help="valida solo el fragmento de un especialista")
    ap.add_argument("--permisivo", action="store_true", help="los avisos de calidad no cambian el código de salida")
    ap.add_argument("--anonimizar", action="store_true", help="enmascara DNI/NIE e IBAN en el HTML generado")
    args = ap.parse_args()
    if not args.validar and not args.fragmento and not args.salida:
        ap.error("--salida es obligatoria salvo con --validar o --fragmento")
    _ANONIMIZAR = args.anonimizar

    data = load(args.fragmentos)
    errores = validate_fragmento(data, args.fragmento) if args.fragmento else validate(data)
    if errores:
        print("ERROR: los fragmentos no son válidos:", file=sys.stderr)
        for e in errores:
            print(f"  - {e}", file=sys.stderr)
        return 1
    avisos = quality(data, args.texto, args.fragmento)

    if args.validar or args.fragmento:
        print("Validación estructural correcta.")
    else:
        out = Path(args.salida)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(data), encoding="utf-8")
        print(f"Informe generado: {out}")
    if avisos:
        print(f"AVISOS de calidad ({len(avisos)}):", file=sys.stderr)
        for a in avisos:
            print(f"  - {a}", file=sys.stderr)
        return 0 if args.permisivo else 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
