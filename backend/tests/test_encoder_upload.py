"""Verifica el helper real de UploadFile sin importar la app ni abrir la DB."""

import ast
import io
from pathlib import Path
from types import SimpleNamespace
from typing import Optional
import unittest


def upload_helper(decoder):
    path = Path(__file__).resolve().parents[1] / "app" / "vectores" / "service.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_embedding_from_upload"
    )
    namespace = {
        "UploadFile": SimpleNamespace,
        "Optional": Optional,
        "np": SimpleNamespace(ndarray=object),
        "embedding_from_image_file": decoder,
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["_embedding_from_upload"]


class EncoderUploadTests(unittest.TestCase):
    def test_upload_is_passed_directly_without_a_full_read_and_is_rewound(self):
        class BoundedReadsOnly(io.BytesIO):
            def read(self, size=-1):
                if size < 0:
                    raise AssertionError("Se volvió a leer toda la imagen en memoria")
                return super().read(size)

        stream = BoundedReadsOnly(b"image-data")
        stream.seek(5)

        def decode(image_file):
            self.assertIs(image_file, stream)
            self.assertEqual(image_file.tell(), 0)
            self.assertEqual(image_file.read(5), b"image")
            return None

        self.assertIsNone(upload_helper(decode)(SimpleNamespace(file=stream)))
        self.assertEqual(stream.tell(), 0)
        self.assertFalse(stream.closed)
        stream.close()

    def test_failed_decoding_also_rewinds_the_upload(self):
        stream = io.BytesIO(b"invalid-image")

        def decode(image_file):
            image_file.read(3)
            raise ValueError("invalid")

        with self.assertRaisesRegex(ValueError, "invalid"):
            upload_helper(decode)(SimpleNamespace(file=stream))
        self.assertEqual(stream.tell(), 0)
        self.assertFalse(stream.closed)
        stream.close()


if __name__ == "__main__":
    unittest.main()
