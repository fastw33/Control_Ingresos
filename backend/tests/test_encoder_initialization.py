"""Pruebas de inicialización sin DB, descargas ni modelos ONNX.

Las dependencias de visión se sustituyen solo al importar el módulo aislado.
Estas pruebas verifican concurrencia y recuperación; no precisión biométrica.
"""

import importlib.util
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


def load_encoder(factory):
    class FaceAnalysisStub:
        def __new__(cls, *args, **kwargs):
            return factory(*args, **kwargs)

    pil = ModuleType("PIL")
    pil.Image = Mock()
    pil.ImageOps = Mock()
    insightface = ModuleType("insightface")
    insightface.__path__ = []
    insightface_app = ModuleType("insightface.app")
    insightface_app.FaceAnalysis = FaceAnalysisStub
    dependencies = {
        "numpy": ModuleType("numpy"),
        "PIL": pil,
        "cv2": ModuleType("cv2"),
        "insightface": insightface,
        "insightface.app": insightface_app,
    }
    path = Path(__file__).resolve().parents[1] / "app" / "vectores" / "Encoder.py"
    spec = importlib.util.spec_from_file_location("isolated_encoder", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict("sys.modules", dependencies):
        spec.loader.exec_module(module)
    return module


class EncoderInitializationTests(unittest.TestCase):
    def test_parallel_first_requests_share_a_fully_prepared_instance(self):
        preparing = Event()
        release_prepare = Event()
        start = Barrier(6)
        instance = SimpleNamespace(prepared=False)

        def prepare(**kwargs):
            preparing.set()
            if not release_prepare.wait(timeout=5):
                raise TimeoutError("La prueba no liberó la preparación")
            instance.prepared = True

        instance.prepare = Mock(side_effect=prepare)
        factory = Mock(return_value=instance)
        encoder = load_encoder(factory)

        def get_app():
            start.wait(timeout=5)
            result = encoder._get_app()
            if not result.prepared:
                raise AssertionError("Se devolvió una instancia sin preparar")
            return result

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(get_app) for _ in range(6)]
            try:
                self.assertTrue(preparing.wait(timeout=5))
                self.assertIsNone(encoder._APP)
            finally:
                release_prepare.set()
            results = [future.result(timeout=5) for future in futures]

        self.assertTrue(all(result is instance for result in results))
        factory.assert_called_once_with(
            name="buffalo_l", allowed_modules=["detection", "recognition"]
        )
        instance.prepare.assert_called_once_with(ctx_id=0, det_size=(640, 640))

    def test_prepare_failure_does_not_cache_an_unusable_instance(self):
        failed = SimpleNamespace(prepare=Mock(side_effect=RuntimeError("prepare")))
        ready = SimpleNamespace(prepare=Mock())
        factory = Mock(side_effect=[failed, ready])
        encoder = load_encoder(factory)

        with self.assertRaisesRegex(RuntimeError, "prepare"):
            encoder._get_app()

        self.assertIsNone(encoder._APP)
        self.assertIs(encoder._get_app(), ready)
        self.assertIs(encoder._get_app(), ready)
        self.assertEqual(factory.call_count, 2)
        ready.prepare.assert_called_once()

    def test_constructor_failure_releases_the_initialization_lock(self):
        ready = SimpleNamespace(prepare=Mock())
        factory = Mock(side_effect=[RuntimeError("load"), ready])
        encoder = load_encoder(factory)

        with self.assertRaisesRegex(RuntimeError, "load"):
            encoder._get_app()

        self.assertIsNone(encoder._APP)
        self.assertTrue(encoder._APP_LOCK.acquire(blocking=False))
        encoder._APP_LOCK.release()
        self.assertIs(encoder._get_app(), ready)
        self.assertEqual(factory.call_count, 2)


if __name__ == "__main__":
    unittest.main()
