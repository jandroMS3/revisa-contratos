"""Pruebas de extracción de PDF y del flujo completo PDF -> texto -> informe.
Ejecutar: python3 -m unittest discover -s .github/skills/extraer-texto-pdf/tests
(necesita pypdf o pdftotext; sin ellos se omiten)."""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _pdf import pdf_bytes

SKILLS = Path(__file__).resolve().parents[2]
EXTRACT = SKILLS / "extraer-texto-pdf" / "scripts" / "extract_pdf.py"
RENDER = SKILLS / "informe-contrato-html" / "scripts" / "render_report.py"
EJEMPLO = json.loads((SKILLS / "informe-contrato-html" / "assets" / "ejemplo.json").read_text(encoding="utf-8"))
HAY_MOTOR = importlib.util.find_spec("pypdf") is not None or shutil.which("pdftotext") is not None

CONTRATO = [
    "CONTRATO DE SERVICIOS\nREUNIDOS\nDe una parte, Acme S.L., y de otra, Persona Ejemplo, acuerdan lo siguiente en este documento.",
    "9. RESPONSABILIDAD\nCláusula 9. El Proveedor responderá de todos los daños y perjuicios sin limitación alguna.",
]


def extraer(*args):
    proc = subprocess.run([sys.executable, str(EXTRACT), *args], capture_output=True, text=True)
    return proc, (json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else None)


@unittest.skipUnless(HAY_MOTOR, "sin pypdf ni pdftotext")
class ExtraccionTest(unittest.TestCase):
    def test_marcadores_de_pagina_indice_y_flujo_completo(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pdf = tmp / "c.pdf"
            pdf.write_bytes(pdf_bytes(CONTRATO))
            proc, resumen = extraer(str(pdf), str(tmp / "t" / "texto.txt"))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            texto = (tmp / "t" / "texto.txt").read_text(encoding="utf-8")
            self.assertIn("=== Página 2 ===", texto)
            self.assertIn("pág 2: 9. RESPONSABILIDAD", (tmp / "t" / "indice.txt").read_text(encoding="utf-8"))
            self.assertEqual(resumen["paginas"], 2)

            # el texto extraído sirve para verificar citas y generar el informe
            frag = tmp / "informe.json"
            frag.write_text(json.dumps(EJEMPLO, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run([sys.executable, str(RENDER), "--texto", str(tmp / "t" / "texto.txt"),
                                "--salida", str(tmp / "informe.html"), str(frag)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_pagina_sin_texto_y_escaneado(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "a.pdf").write_bytes(pdf_bytes([CONTRATO[1], ""]))
            proc, resumen = extraer(str(tmp / "a.pdf"), str(tmp / "a.txt"))
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(resumen["paginas_sin_texto"], [2])
            self.assertIn("ocr_sugerido", resumen)

            (tmp / "b.pdf").write_bytes(pdf_bytes(["", ""]))
            proc, resumen = extraer(str(tmp / "b.pdf"), str(tmp / "b.txt"))
            self.assertEqual(proc.returncode, 2)
            self.assertTrue(resumen["posible_escaneado"])

    def test_anexo_continua_la_numeracion(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "c.pdf").write_bytes(pdf_bytes(CONTRATO))
            (tmp / "anexo.pdf").write_bytes(pdf_bytes(["ANEXO 1\nTarifas aplicables al servicio durante la vigencia del contrato firmado."]))
            proc, resumen = extraer(str(tmp / "c.pdf"), str(tmp / "t.txt"), "--anexo", str(tmp / "anexo.pdf"))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            texto = (tmp / "t.txt").read_text(encoding="utf-8")
            self.assertIn("=== Documento: anexo.pdf ===\n=== Página 3 ===", texto)
            self.assertEqual(resumen["documentos"][1], {"archivo": "anexo.pdf", "desde_pagina": 3})

    def test_archivo_inexistente(self):
        proc, _ = extraer("/no/existe.pdf", "/tmp/x.txt")
        self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
