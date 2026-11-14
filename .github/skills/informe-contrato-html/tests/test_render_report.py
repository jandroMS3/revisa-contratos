"""Pruebas del renderizador. Ejecutar: python3 -m unittest discover -s .github/skills/informe-contrato-html/tests"""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts" / "render_report.py"
EJEMPLO = json.loads((SKILL / "assets" / "ejemplo.json").read_text(encoding="utf-8"))
TEXTO = "Cláusula 9. El Proveedor responderá de todos los daños y perjuicios sin limitación alguna."


class RenderTest(unittest.TestCase):
    def run_script(self, data, *extra, texto=TEXTO):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "f.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            (tmp / "texto.txt").write_text(texto, encoding="utf-8")
            salida = tmp / "informe.html"
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--texto", str(tmp / "texto.txt"), "--salida", str(salida), *extra, str(tmp / "f.json")],
                capture_output=True, text=True)
            html = salida.read_text(encoding="utf-8") if salida.exists() else None
            return proc, html

    def mutate(self, fn):
        d = copy.deepcopy(EJEMPLO)
        fn(d)
        return d

    def test_ejemplo_correcto(self):
        proc, html = self.run_script(EJEMPLO)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('id="riesgo-R1"', html)
        self.assertIn("Qué negociar primero", html)

    def test_contenido_escapado(self):
        d = self.mutate(lambda d: d.update(titulo="<script>alert(1)</script>"))
        _, html = self.run_script(d)
        self.assertNotIn("<script>alert", html)

    def test_severidad_invalida_es_error(self):
        proc, html = self.run_script(self.mutate(lambda d: d["riesgos"][0].update(severidad="grave")))
        self.assertEqual(proc.returncode, 1)
        self.assertIsNone(html)

    def test_id_duplicado_y_referencia_rota(self):
        def f(d):
            d["riesgos"].append(copy.deepcopy(d["riesgos"][0]))
            d["mejoras"][0]["riesgo_relacionado"] = "R9"
        proc, _ = self.run_script(self.mutate(f))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("duplicado", proc.stderr)
        self.assertIn("'R9' no existe", proc.stderr)

    def test_cita_inventada_da_aviso(self):
        proc, html = self.run_script(self.mutate(lambda d: d["riesgos"][0].update(cita="El Proveedor pagará todas las costas del proceso judicial")))
        self.assertEqual(proc.returncode, 3)
        self.assertIn("no encontrada", proc.stderr)
        self.assertIsNotNone(html)

    def test_cita_corta_da_aviso(self):
        proc, _ = self.run_script(self.mutate(lambda d: d["riesgos"][0].update(cita="El Proveedor")))
        self.assertEqual(proc.returncode, 3)
        self.assertIn("demasiado corta", proc.stderr)

    def test_cita_de_punto_clave_se_verifica(self):
        proc, _ = self.run_script(self.mutate(lambda d: d["puntos_clave"][0].update(cita="Las facturas se pagarán a los noventa días de su recepción")))
        self.assertEqual(proc.returncode, 3)
        self.assertIn("puntos_clave", proc.stderr)

    def test_riesgo_sin_mejora_da_aviso(self):
        def f(d):
            d["mejoras"] = [{"titulo": "x", "prioridad": "baja"}]
        proc, _ = self.run_script(self.mutate(f))
        self.assertEqual(proc.returncode, 3)
        self.assertIn("sin mejora", proc.stderr)

    def test_mejora_puede_cubrir_varios_riesgos(self):
        def f(d):
            d["riesgos"].append({**d["riesgos"][0], "id": "R2", "severidad": "medio"})
            d["mejoras"][0]["riesgo_relacionado"] = ["R1", "R2"]
        proc, _ = self.run_script(self.mutate(f))
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_veredicto_inferior_al_riesgo_maximo(self):
        proc, _ = self.run_script(self.mutate(lambda d: d["veredicto"].update(nivel="bajo")))
        self.assertEqual(proc.returncode, 3)
        self.assertIn("inferior", proc.stderr)

    def test_permisivo_y_validar(self):
        d = self.mutate(lambda d: d["riesgos"][0].update(cita="El Proveedor"))
        self.assertEqual(self.run_script(d, "--permisivo")[0].returncode, 0)
        proc, html = self.run_script(d, "--validar")
        self.assertEqual(proc.returncode, 3)
        self.assertIsNone(html)


TEXTO_PAGINAS = (
    "=== Página 1 ===\nPreámbulo del contrato de servicios entre las partes.\n\n"
    "=== Página 2 ===\nCláusula 9. El Proveedor responderá de todos los daños y perjuicios sin limitación alguna.\n\n"
    "=== Página 3 ===\nCláusula 12. Las facturas se pagarán a noventa días desde su recepción en destino.\n"
)


class RenderMejorasTest(unittest.TestCase):
    """Validaciones añadidas: citas múltiples, páginas, veredicto, fragmentos, anonimizado y HTML interactivo."""
    run_script = RenderTest.run_script
    mutate = RenderTest.mutate

    def test_citas_adicionales_se_verifican(self):
        d = self.mutate(lambda d: d["riesgos"][0].update(citas=["El Proveedor pagará todas las costas del proceso"]))
        proc, _ = self.run_script(d)
        self.assertEqual(proc.returncode, 3)
        self.assertIn("no encontrada", proc.stderr)

    def test_pagina_distinta_a_la_indicada_da_aviso(self):
        malo = self.mutate(lambda d: d["riesgos"][0].update(clausula="Cláusula 9 (pág. 5)"))
        bueno = self.mutate(lambda d: d["riesgos"][0].update(clausula="Cláusula 9 (pág. 2)"))
        proc, _ = self.run_script(malo, texto=TEXTO_PAGINAS)
        self.assertEqual(proc.returncode, 3)
        self.assertIn("pág. 2 pero la cláusula indica pág. 5", proc.stderr)
        self.assertEqual(self.run_script(bueno, texto=TEXTO_PAGINAS)[0].returncode, 0)

    def test_cita_repartida_entre_paginas_no_da_aviso_de_pagina(self):
        d = self.mutate(lambda d: d["riesgos"][0].update(
            clausula="Cláusula 9 (págs. 1-2)", cita="Preámbulo del contrato de servicios entre las partes. Cláusula 9. El Proveedor responderá"))
        self.assertEqual(self.run_script(d, texto=TEXTO_PAGINAS)[0].returncode, 0)

    def test_recuentos_del_veredicto_deben_cuadrar(self):
        d = self.mutate(lambda d: d["veredicto"].update(texto="Se han detectado 3 riesgos críticos y 2 altos."))
        proc, _ = self.run_script(d)
        self.assertEqual(proc.returncode, 3)
        self.assertIn("«3 críticos»", proc.stderr)
        ok = self.mutate(lambda d: d["veredicto"].update(texto="Hay 1 riesgo crítico y 30 meses de plazo."))
        self.assertEqual(self.run_script(ok)[0].returncode, 0)

    def test_falta_fecha_de_analisis_da_aviso(self):
        proc, _ = self.run_script(self.mutate(lambda d: d.pop("fecha_analisis")))
        self.assertEqual(proc.returncode, 3)
        self.assertIn("fecha_analisis", proc.stderr)

    def test_riesgo_de_anexo_visual_no_exige_cita_y_se_marca(self):
        def f(d):
            d["riesgos"][0].update(origen="anexo-visual")
            d["riesgos"][0].pop("cita")
        proc, html = self.run_script(self.mutate(f))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Leído de imagen", html)

    def test_origen_invalido_es_error(self):
        proc, _ = self.run_script(self.mutate(lambda d: d["riesgos"][0].update(origen="magia")))
        self.assertEqual(proc.returncode, 1)

    def test_anonimizar_enmascara_dni_e_iban(self):
        def f(d):
            d["partes"][1]["detalle"] = "DNI 12345678Z, IBAN ES45 2045 6037 4630 0006 0102"
        d = self.mutate(f)
        _, normal = self.run_script(d)
        _, anonimo = self.run_script(d, "--anonimizar")
        self.assertIn("12345678Z", normal)
        self.assertNotIn("12345678Z", anonimo)
        self.assertNotIn("4630 0006", anonimo)
        self.assertIn("ES45", anonimo)

    def test_fragmento_riesgos_valida_solo_ese_fragmento(self):
        solo = {"riesgos": EJEMPLO["riesgos"]}
        self.assertEqual(self.run_script(solo, "--fragmento", "riesgos")[0].returncode, 0)
        malo = {"riesgos": [{**EJEMPLO["riesgos"][0], "severidad": "grave"}]}
        proc, _ = self.run_script(malo, "--fragmento", "riesgos")
        self.assertEqual(proc.returncode, 1)
        citado = {"riesgos": [{**EJEMPLO["riesgos"][0], "cita": "El Proveedor pagará todas las costas del proceso judicial"}]}
        self.assertEqual(self.run_script(citado, "--fragmento", "riesgos")[0].returncode, 3)

    def test_fragmento_mejoras_comprueba_referencias_con_riesgos(self):
        roto = {"riesgos": EJEMPLO["riesgos"], "mejoras": [{**EJEMPLO["mejoras"][0], "riesgo_relacionado": "R7"}]}
        proc, _ = self.run_script(roto, "--fragmento", "mejoras")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("'R7' no existe", proc.stderr)
        sin_cubrir = {"riesgos": EJEMPLO["riesgos"], "mejoras": [{"titulo": "x", "prioridad": "baja"}]}
        self.assertEqual(self.run_script(sin_cubrir, "--fragmento", "mejoras")[0].returncode, 3)

    def test_html_enlaza_riesgos_y_mejoras_y_es_interactivo(self):
        _, html = self.run_script(EJEMPLO)
        self.assertIn('<details id="riesgo-R1"', html)
        self.assertIn('href="#mejora-M1"', html)
        self.assertIn('id="mejora-M1"', html)
        self.assertIn('href="#riesgo-R1"', html)
        self.assertIn('data-sev="critico"', html)
        self.assertIn('class="copiar"', html)
        self.assertIn("IntersectionObserver", html)


if __name__ == "__main__":
    unittest.main()
