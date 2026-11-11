"""Contratos del pipeline; no sustituye la validación con modelos y fotos reales."""

from concurrent.futures import ThreadPoolExecutor
import io
from threading import Barrier, Event, Lock
from types import SimpleNamespace
import unittest
import weakref

from test_encoder_initialization import load_encoder


class Boxes:
    def __init__(self, rows):
        self.rows = rows
        self.shape = (len(rows), 5)

    def __getitem__(self, index):
        row, column = index
        return self.rows[row][column]


class Vector:
    def astype(self, dtype):
        if dtype != "float32":
            raise AssertionError("El formato del embedding cambió")
        return self


class RGBBuffer:
    pass


class EncoderFaceSelectionTests(unittest.TestCase):
    def test_largest_face_uses_original_keypoints_and_only_one_embedding(self):
        encoder, dependencies = load_encoder()
        boxes = Boxes([
            (0, 0, 10, 10, 0.99),
            (100, 100, 140, 140, 0.8),
            (0, 0, 30, 30, 0.95),
        ])
        keypoints = [object(), object(), object()]
        vector, image = Vector(), object()
        dependencies.detector.detect.return_value = boxes, keypoints

        def recognize(received_image, face):
            self.assertIs(received_image, image)
            self.assertEqual(face.bbox, boxes.rows[1][:4])
            self.assertIs(face.kps, keypoints[1])
            self.assertEqual(face.det_score, 0.8)
            face.normed_embedding = vector

        dependencies.recognizer.get.side_effect = recognize
        result = encoder._get_app().embedding_from_bgr(image)
        self.assertIs(result, vector)
        dependencies.recognizer.get.assert_called_once()
        dependencies.detector.detect.assert_called_once_with(
            image, max_num=0, metric="default"
        )

    def test_equal_areas_keep_the_first_face_and_negative_sizes_do_not_win(self):
        encoder, dependencies = load_encoder()
        boxes = Boxes([
            (10, 10, -90, -90, 0.99),
            (0, 0, 20, 20, 0.8),
            (100, 100, 120, 120, 0.9),
        ])
        dependencies.detector.detect.return_value = boxes, None
        vector = Vector()

        def recognize(image, face):
            self.assertEqual(face.bbox, boxes.rows[1][:4])
            self.assertIsNone(face.kps)
            face.normed_embedding = vector

        dependencies.recognizer.get.side_effect = recognize
        self.assertIs(encoder._get_app().embedding_from_bgr(object()), vector)
        dependencies.recognizer.get.assert_called_once()

    def test_no_faces_does_not_run_the_recognizer(self):
        encoder, dependencies = load_encoder()
        dependencies.detector.detect.return_value = Boxes([]), None
        self.assertIsNone(encoder._get_app().embedding_from_bgr(object()))
        dependencies.recognizer.get.assert_not_called()


class EncoderMemoryLifetimeTests(unittest.TestCase):
    def test_rgb_is_released_before_inference_and_lock_precedes_decode(self):
        encoder, _ = load_encoder()
        references = []
        bgr, result = object(), Vector()

        def decode(image_file):
            self.assertTrue(encoder._INFERENCE_LOCK.locked())
            rgb = RGBBuffer()
            references.append(weakref.ref(rgb))
            return rgb

        def convert(rgb, conversion):
            self.assertIs(references[0](), rgb)
            return bgr

        def infer(image):
            self.assertTrue(encoder._INFERENCE_LOCK.locked())
            self.assertIs(image, bgr)
            self.assertIsNone(references[0]())
            return result

        encoder._load_image_fix_orientation = decode
        encoder.cv2.COLOR_RGB2BGR = 1
        encoder.cv2.cvtColor = convert
        encoder._get_app = lambda: SimpleNamespace(embedding_from_bgr=infer)
        self.assertIs(encoder.embedding_from_image_file(io.BytesIO()), result)
        self.assertFalse(encoder._INFERENCE_LOCK.locked())

    def test_concurrent_requests_do_not_overlap_decoded_images(self):
        encoder, _ = load_encoder()
        start = Barrier(6)
        first_inference, release_first = Event(), Event()
        counter_lock = Lock()
        active = peak = decoded = 0

        def decode(image_file):
            nonlocal active, peak, decoded
            with counter_lock:
                active += 1
                decoded += 1
                peak = max(peak, active)
            return RGBBuffer()

        def infer(image):
            nonlocal active
            first_inference.set()
            if not release_first.wait(timeout=5):
                raise TimeoutError("La prueba no liberó la inferencia")
            with counter_lock:
                active -= 1
            return None

        encoder._load_image_fix_orientation = decode
        encoder.cv2.COLOR_RGB2BGR = 1
        encoder.cv2.cvtColor = lambda rgb, conversion: object()
        encoder._get_app = lambda: SimpleNamespace(embedding_from_bgr=infer)

        def request():
            start.wait(timeout=5)
            return encoder.embedding_from_image_file(io.BytesIO())

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(request) for _ in range(6)]
            try:
                self.assertTrue(first_inference.wait(timeout=5))
                with counter_lock:
                    self.assertEqual(decoded, 1)
            finally:
                release_first.set()
            for future in futures:
                self.assertIsNone(future.result(timeout=5))

        self.assertEqual(peak, 1)
        self.assertEqual(decoded, 6)
        self.assertEqual(active, 0)

    def test_decode_or_inference_failure_releases_the_lock(self):
        for stage in ("decode", "inference"):
            with self.subTest(stage=stage):
                encoder, _ = load_encoder()
                encoder.cv2.COLOR_RGB2BGR = 1
                encoder.cv2.cvtColor = lambda rgb, conversion: object()

                def decode(image_file):
                    if stage == "decode":
                        raise ValueError("decode")
                    return RGBBuffer()

                def infer(image):
                    raise ValueError("inference")

                encoder._load_image_fix_orientation = decode
                encoder._get_app = lambda: SimpleNamespace(embedding_from_bgr=infer)
                with self.assertRaisesRegex(ValueError, stage):
                    encoder.embedding_from_image_file(io.BytesIO())
                self.assertFalse(encoder._INFERENCE_LOCK.locked())

                encoder._load_image_fix_orientation = lambda image_file: RGBBuffer()
                encoder._get_app = lambda: SimpleNamespace(embedding_from_bgr=lambda _: None)
                self.assertIsNone(encoder.embedding_from_image_file(io.BytesIO()))

    def test_existing_bytes_api_preserves_input_and_closes_its_stream(self):
        encoder, _ = load_encoder()
        seen, result = [], Vector()

        def process(image_file):
            self.assertEqual(image_file.read(), b"original-image")
            seen.append(image_file)
            return result

        encoder.embedding_from_image_file = process
        self.assertIs(encoder.embedding_from_image_bytes(b"original-image"), result)
        self.assertTrue(seen[0].closed)


class EncoderImageDecodingTests(unittest.TestCase):
    def test_pixels_match_previous_decoding_for_rgb_rgba_cmyk_and_exif(self):
        try:
            from PIL import Image, ImageOps
        except ImportError:
            self.skipTest("Pillow no está disponible en este intérprete")

        encoder, _ = load_encoder()
        encoder.Image, encoder.ImageOps = Image, ImageOps
        encoder.np.asarray = lambda image: (image.size, image.mode, image.tobytes())

        for mode, format_, orientation in (
            ("RGB", "PNG", None), ("RGBA", "PNG", None),
            ("CMYK", "JPEG", None), ("RGB", "JPEG", 6),
        ):
            with self.subTest(mode=mode, orientation=orientation):
                image_file = io.BytesIO()
                with Image.new(mode, (4, 2)) as image:
                    image.putpixel((0, 0), {
                        "RGB": (240, 60, 20),
                        "RGBA": (240, 60, 20, 100),
                        "CMYK": (10, 100, 200, 30),
                    }[mode])
                    if orientation:
                        exif = Image.Exif()
                        exif[274] = orientation
                        image.save(image_file, format=format_, exif=exif)
                    else:
                        image.save(image_file, format=format_)
                image_file.seek(0)
                with Image.open(io.BytesIO(image_file.getvalue())) as source:
                    with ImageOps.exif_transpose(source) as oriented:
                        with oriented.convert("RGB") as rgb:
                            expected = (rgb.size, rgb.mode, rgb.tobytes())
                actual = encoder._load_image_fix_orientation(image_file)
                self.assertEqual(actual, expected)
                self.assertFalse(image_file.closed)
                image_file.close()


if __name__ == "__main__":
    unittest.main()
