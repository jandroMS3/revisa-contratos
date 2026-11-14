"""Pruebas del comparador. Ejecutar: python3 -m unittest discover -s .github/skills/informe-contrato-html/tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "comparar_versiones.py"


def riesgo(i, titulo, sev, cita):
    return {"id": i, "titulo": titulo, "severidad": sev, "cita": cita}


class CompararTest(unittest.TestCase):
    def escribir(self, carpeta: Path, riesgos, nivel, texto="mismo texto"):
        carpeta.mkdir()
        (carpeta / "texto.txt").write_text(texto, encoding="utf-8")
        (carpeta / "riesgos.json").write_text(json.dumps({"riesgos": riesgos}), encoding="utf-8")
        (carpeta / "veredicto.json").write_text(json.dumps({"veredicto": {"nivel": nivel}}), encoding="utf-8")

    def test_detecta_nuevos_eliminados_y_cambios_de_severidad_pese_a_renumeracion(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self.escribir(tmp / "a", [
                riesgo("R1", "Plazo de entrega elástico", "alto", "El plazo máximo de entrega será de veinte meses"),
                riesgo("R2", "Penalización del 20 %", "alto", "retendrá como propias todas las cantidades"),
                riesgo("R3", "Fuero en Valencia", "bajo", "se someten al Tribunal de Instancia de Valencia"),
            ], "alto")
            self.escribir(tmp / "n", [
                riesgo("R1", "Penalización del 20 %", "alto", "retendrá como propias todas las cantidades"),
                riesgo("R2", "Plazo de entrega elástico", "critico", "El plazo máximo de entrega será de veinte meses"),
                riesgo("R3", "Licencia condicionada", "medio", "licencia supeditada a la presentación del proyecto"),
            ], "critico")
            proc = subprocess.run([sys.executable, str(SCRIPT), str(tmp / "a"), str(tmp / "n")], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("alto → critico", proc.stdout)
            self.assertIn("Licencia condicionada", proc.stdout.split("Nuevos")[1].split("###")[0])
            self.assertIn("Fuero en Valencia", proc.stdout.split("Ya no aparecen")[1])
            self.assertIn("idéntico", proc.stdout)

    def test_detecta_cambio_en_el_texto(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self.escribir(tmp / "a", [], "bajo", texto="uno\ndos")
            self.escribir(tmp / "n", [], "bajo", texto="uno\ntres\ncuatro")
            proc = subprocess.run([sys.executable, str(SCRIPT), str(tmp / "a"), str(tmp / "n")], capture_output=True, text=True)
            self.assertIn("1 líneas eliminadas y 2 añadidas", proc.stdout)

    def test_carpeta_inexistente(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "/no/existe", "/tampoco"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
