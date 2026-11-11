"""Inicialización del motor aislada de DB, descargas y ejecución ONNX real."""

import importlib.util
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


def load_encoder():
    detector = Mock(taskname="detection")
    recognizer = Mock(taskname="recognition")

    def model_for_path(path, **kwargs):
        return {
            "det_10g.onnx": detector,
            "w600k_r50.onnx": recognizer,
        }[Path(path).name]

    model_loader = Mock(side_effect=model_for_path)
    ensure_available = Mock(return_value="/fake/models/buffalo_l")
    pil = ModuleType("PIL")
    pil.Image, pil.ImageOps = Mock(), Mock()
    insightface = ModuleType("insightface")
    insightface.__path__ = []
    insightface_app = ModuleType("insightface.app")
    insightface_app.__path__ = []
    common = ModuleType("insightface.app.common")
    common.Face = SimpleNamespace
    model_zoo = ModuleType("insightface.model_zoo")
    model_zoo.get_model = model_loader
    utils = ModuleType("insightface.utils")
    utils.ensure_available = ensure_available
    dependencies = {
        "numpy": ModuleType("numpy"),
        "PIL": pil,
        "cv2": ModuleType("cv2"),
        "insightface": insightface,
        "insightface.app": insightface_app,
        "insightface.app.common": common,
        "insightface.model_zoo": model_zoo,
        "insightface.utils": utils,
    }
    path = Path(__file__).resolve().parents[1] / "app" / "vectores" / "Encoder.py"
    spec = importlib.util.spec_from_file_location("isolated_encoder", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict("sys.modules", dependencies):
        spec.loader.exec_module(module)
    return module, SimpleNamespace(
        detector=detector,
        recognizer=recognizer,
        model_loader=model_loader,
        ensure_available=ensure_available,
    )


class EncoderInitializationTests(unittest.TestCase):
    def test_parallel_first_requests_share_a_fully_prepared_instance(self):
        encoder, dependencies = load_encoder()
        preparing, release_prepare = Event(), Event()
        start = Barrier(6)

        def prepare(**kwargs):
            preparing.set()
            if not release_prepare.wait(timeout=5):
                raise TimeoutError("La prueba no liberó la preparación")

        dependencies.detector.prepare.side_effect = prepare

        def get_app():
            start.wait(timeout=5)
            result = encoder._get_app()
            if dependencies.recognizer.prepare.call_count != 1:
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

        self.assertTrue(all(result is results[0] for result in results))
        calls = dependencies.model_loader.call_args_list
        self.assertEqual(
            [Path(call.args[0]).name for call in calls],
            ["det_10g.onnx", "w600k_r50.onnx"],
        )
        for call in calls:
            self.assertEqual(call.kwargs["providers"], ["CPUExecutionProvider"])
        dependencies.ensure_available.assert_called_once_with(
            "models", "buffalo_l", root="~/.insightface"
        )
        dependencies.detector.prepare.assert_called_once_with(
            ctx_id=0, input_size=(640, 640), det_thresh=0.5
        )
        dependencies.recognizer.prepare.assert_called_once_with(ctx_id=0)

    def test_prepare_failure_does_not_cache_an_unusable_instance(self):
        for component in ("detector", "recognizer"):
            with self.subTest(component=component):
                encoder, dependencies = load_encoder()
                model = getattr(dependencies, component)
                model.prepare.side_effect = [RuntimeError("prepare"), None]
                with self.assertRaisesRegex(RuntimeError, "prepare"):
                    encoder._get_app()
                self.assertIsNone(encoder._APP)
                ready = encoder._get_app()
                self.assertIs(encoder._get_app(), ready)
                self.assertEqual(dependencies.model_loader.call_count, 4)

    def test_constructor_failure_releases_the_initialization_lock(self):
        encoder, dependencies = load_encoder()
        dependencies.model_loader.side_effect = [
            RuntimeError("load"), dependencies.detector, dependencies.recognizer,
        ]
        with self.assertRaisesRegex(RuntimeError, "load"):
            encoder._get_app()
        self.assertIsNone(encoder._APP)
        self.assertTrue(encoder._APP_LOCK.acquire(blocking=False))
        encoder._APP_LOCK.release()
        ready = encoder._get_app()
        self.assertIs(encoder._get_app(), ready)

    def test_incompatible_models_are_not_cached(self):
        encoder, dependencies = load_encoder()
        dependencies.recognizer.taskname = "landmark_2d_106"
        with self.assertRaisesRegex(RuntimeError, "reconocimiento"):
            encoder._get_app()
        self.assertIsNone(encoder._APP)
        dependencies.detector.prepare.assert_not_called()


if __name__ == "__main__":
    unittest.main()
