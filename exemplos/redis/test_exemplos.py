"""Testes dos programas completos em Redis real, incluindo limpeza das chaves."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

from _conexao import conectar

PASTA = Path(__file__).resolve().parent


class ExemplosRedis(unittest.TestCase):
    def rodar(self, arquivo):
        processo = subprocess.run([sys.executable, str(PASTA / arquivo)],
                                  capture_output=True, text=True, timeout=20, check=True)
        resultado = json.loads(processo.stdout)
        self.assertTrue(resultado["prefixo"].startswith("demo:"))
        with conectar() as banco:
            self.assertEqual(list(banco.scan_iter(match=resultado["prefixo"] + ":*", count=10000)), [])
        return resultado

    def test_crud_e_limpeza(self):
        resultado = self.rodar("01_crud_hash.py")
        self.assertEqual(resultado["criada"]["temperature_centi"], "2850")
        self.assertEqual(resultado["atualizada"]["temperature_centi"], "3300")
        self.assertEqual(resultado["criada"]["humidity_centi"], "6100")
        self.assertTrue(resultado["excluida"])

    def test_historico_inclusivo_ordenado_e_limpeza(self):
        resultado = self.rodar("02_historico_sensor.py")
        self.assertEqual(resultado["ids"], ["2", "3"])
        self.assertEqual([r["ts"] for r in resultado["leituras"]], ["1793491500", "1793491800"])
        self.assertEqual([r["temperature_centi"] for r in resultado["leituras"]], ["2900", "2950"])

    def test_cache_ausencia_acerto_expiracao_e_limpeza(self):
        resultado = self.rodar("03_cache_ttl.py")
        self.assertTrue(resultado["ausente_antes"])
        self.assertEqual(resultado["acerto"], {"sensor_id": 1, "leituras": 3, "temperatura_media": 29.0})
        self.assertIn(resultado["ttl_segundos_observado"], (0, 1, 2))
        self.assertTrue(resultado["expirou"])


if __name__ == "__main__":
    unittest.main()
