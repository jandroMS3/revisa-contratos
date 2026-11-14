"""Pruebas de los scripts de gestión. Ejecutar: python3 -m unittest discover -s .github/skills/informe-contrato-html/tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
EJEMPLO = json.loads((SKILL / "assets" / "ejemplo.json").read_text(encoding="utf-8"))
TEXTO = "Cláusula 9. El Proveedor responderá de todos los daños y perjuicios sin limitación alguna."


def ejecutar(script, *args, cwd):
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True, cwd=cwd)


class PrepararRevisionTest(unittest.TestCase):
    def test_slug_versiones_y_carpeta_incompleta(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "contratos").mkdir()
            pdf = tmp / "contratos" / "Mi Contrato Ñandú (Final).pdf"
            pdf.write_bytes(b"uno")

            r1 = json.loads(ejecutar("preparar_revision.py", str(pdf), cwd=tmp).stdout)
            self.assertEqual((r1["slug"], r1["version"], r1["version_anterior"]), ("mi-contrato-nandu-final", 1, None))
            self.assertTrue((tmp / r1["carpeta_trabajo"]).is_dir())

            # sin informe: la ejecución quedó a medias y se reutiliza la carpeta
            r1b = json.loads(ejecutar("preparar_revision.py", str(pdf), cwd=tmp).stdout)
            self.assertEqual(r1b["slug"], r1["slug"])
            self.assertTrue(r1b["reutiliza_carpeta_incompleta"])

            (tmp / r1["informe"]).write_text("<html></html>", encoding="utf-8")
            r2 = json.loads(ejecutar("preparar_revision.py", str(pdf), cwd=tmp).stdout)
            self.assertEqual((r2["slug"], r2["version_anterior"], r2["pdf_cambiado"]), ("mi-contrato-nandu-final-v2", r1["slug"], False))

            pdf.write_bytes(b"dos")
            (tmp / r2["informe"]).write_text("<html></html>", encoding="utf-8")
            r3 = json.loads(ejecutar("preparar_revision.py", str(pdf), cwd=tmp).stdout)
            self.assertEqual((r3["slug"], r3["pdf_cambiado"]), ("mi-contrato-nandu-final-v3", True))

    def test_forzar_nueva_ignora_la_carpeta_incompleta(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pdf = tmp / "a.pdf"
            pdf.write_bytes(b"x")
            ejecutar("preparar_revision.py", str(pdf), cwd=tmp)
            r = json.loads(ejecutar("preparar_revision.py", str(pdf), "--forzar-nueva", "--no-crear", cwd=tmp).stdout)
            self.assertEqual(r["slug"], "a-v2")

    def test_pdf_inexistente(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(ejecutar("preparar_revision.py", "no.pdf", cwd=tmp).returncode, 1)


class IntegridadTest(unittest.TestCase):
    def montar(self, tmp: Path):
        for rel, contenido in {
            "contratos/a.pdf": "pdf",
            "informes/.trabajo/s/texto.txt": "t",
            "informes/.trabajo/s-anterior/riesgos.json": "{}",
            ".venv/lib/x.py": "ignorado",
        }.items():
            (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp / rel).write_text(contenido, encoding="utf-8")

    def test_permite_lo_propio_y_detecta_lo_ajeno(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self.montar(tmp)
            self.assertEqual(ejecutar("integridad.py", "guardar", "s", cwd=tmp).returncode, 0)

            (tmp / "informes/.trabajo/s/resumen.json").write_text("{}", encoding="utf-8")
            (tmp / "informes/s-informe.html").write_text("<html>", encoding="utf-8")
            (tmp / ".venv/lib/x.py").write_text("cambia", encoding="utf-8")
            self.assertEqual(ejecutar("integridad.py", "comprobar", "s", cwd=tmp).returncode, 0)

            (tmp / "informes/.trabajo/s-anterior/riesgos.json").write_text('{"x":1}', encoding="utf-8")
            (tmp / "contratos/otro.txt").write_text("nuevo", encoding="utf-8")
            proc = ejecutar("integridad.py", "comprobar", "s", cwd=tmp)
            res = json.loads(proc.stdout)
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(res["modificados"], ["informes/.trabajo/s-anterior/riesgos.json"])
            self.assertEqual(res["nuevos"], ["contratos/otro.txt"])

    def test_sin_instantanea_falla(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(ejecutar("integridad.py", "comprobar", "s", cwd=tmp).returncode, 1)


class RegenerarTodosTest(unittest.TestCase):
    def fragmentos(self):
        e = EJEMPLO
        return {
            "meta": {k: e[k] for k in ("titulo", "archivo", "rol_usuario", "tipo_contrato", "jurisdiccion", "fecha_analisis", "advertencias")},
            "resumen": {k: e[k] for k in ("resumen", "partes", "datos_clave", "puntos_clave", "fechas_plazos", "obligaciones")},
            "riesgos": {k: e[k] for k in ("riesgos", "clausulas_ausentes")},
            "mejoras": {k: e[k] for k in ("mejoras", "preguntas_abiertas")},
            "veredicto": {"veredicto": e["veredicto"]},
        }

    def test_regenera_los_completos_y_omite_los_incompletos(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            completo = tmp / "informes/.trabajo/uno"
            completo.mkdir(parents=True)
            for nombre, contenido in self.fragmentos().items():
                (completo / f"{nombre}.json").write_text(json.dumps(contenido, ensure_ascii=False), encoding="utf-8")
            (completo / "texto.txt").write_text(TEXTO, encoding="utf-8")
            (tmp / "informes/.trabajo/dos").mkdir()
            (tmp / "informes/.trabajo/dos/meta.json").write_text("{}", encoding="utf-8")

            proc = ejecutar("regenerar_todos.py", cwd=tmp)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("uno: correcto", proc.stdout)
            self.assertIn("dos: omitido", proc.stdout)
            self.assertIn("<details", (tmp / "informes/uno-informe.html").read_text(encoding="utf-8"))


class PaginasCambiadasTest(unittest.TestCase):
    def test_lista_paginas_modificadas_nuevas_y_eliminadas(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for nombre, texto in {
                "a": "=== Página 1 ===\nuno\n\n=== Página 2 ===\ndos\n\n=== Página 3 ===\ntres\n",
                "n": "=== Página 1 ===\nuno\n\n=== Página 2 ===\ndos cambiado\n",
            }.items():
                (tmp / nombre).mkdir()
                (tmp / nombre / "texto.txt").write_text(texto, encoding="utf-8")
            proc = ejecutar("comparar_versiones.py", str(tmp / "a"), str(tmp / "n"), "--paginas", cwd=tmp)
            self.assertEqual(json.loads(proc.stdout), {"modificadas": [2], "nuevas": [], "eliminadas": [3]})


if __name__ == "__main__":
    unittest.main()
