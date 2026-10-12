"""Configuración común: fecha fija y directorios de operación aislados por prueba."""

import pytest


@pytest.fixture(autouse=True)
def entorno_aislado(tmp_path, monkeypatch):
    monkeypatch.setenv("FECHA_REFERENCIA", "2026-09-29")
    monkeypatch.setenv("DATOS_OPERACION_DIR", str(tmp_path / "operacion"))
    monkeypatch.setenv("AUDITORIA_RUTA", str(tmp_path / "auditoria.jsonl"))
    monkeypatch.delenv("SIMULAR_FALLA_TRANSPORTADORA", raising=False)
    monkeypatch.delenv("TRACKINGS_CON_FALLA", raising=False)
    return tmp_path
