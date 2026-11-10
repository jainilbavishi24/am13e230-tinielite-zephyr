import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.generate_model_adapter import generate_adapter, render_adapter
from tools.model_package import ModelPackageError, load_model_package


class ModelPackageTests(unittest.TestCase):
    def make_package(self, root: Path) -> Path:
        package = root / "alternate_classifier"
        (package / "artifacts").mkdir(parents=True)
        (package / "golden_vectors").mkdir()
        library = package / "artifacts" / "alternate.a"
        library.write_bytes(b"synthetic archive used only by the manifest unit test")
        (package / "artifacts" / "alternate.h").write_text(
            "#include <stdint.h>\n"
            "extern volatile int32_t alternate_finished;\n"
            "struct alternate_inputs { void *sensor_input; };\n"
            "struct alternate_outputs { void *scores; };\n"
            "int32_t alternate_run(struct alternate_inputs *, "
            "struct alternate_outputs *);\n"
        )
        (package / "golden_vectors" / "vectors.json").write_text("[]\n")

        model_id = int.from_bytes(hashlib.sha256(library.read_bytes()).digest()[:4], "big")
        manifest = {
            "schema_version": 1,
            "name": "alternate_classifier",
            "display_name": "Synthetic alternate classifier",
            "model_id": f"0x{model_id:08x}",
            "target": {
                "device_family": "AM13E2",
                "accelerator": "TINIElite",
                "requires_npu": True,
            },
            "artifacts": {
                "library": "artifacts/alternate.a",
                "header": "artifacts/alternate.h",
                "entry_symbol": "alternate_run",
            },
            "runtime": {
                "input_struct": "alternate_inputs",
                "output_struct": "alternate_outputs",
                "completion_symbol": "alternate_finished",
                "continuation_symbol": "alternate_continue",
            },
            "input": {
                "shape": [1, 64],
                "dtype": "int8",
                "size_bytes": 64,
                "runtime_field": "sensor_input",
            },
            "output": {
                "shape": [1, 4],
                "dtype": "int16",
                "size_bytes": 8,
                "runtime_field": "scores",
                "labels": ["a", "b", "c", "d"],
            },
            "preprocessing": {
                "type": "ti_affine_shift_header",
                "bias_symbol": "alternate_bias",
                "scale_symbol": "alternate_scale",
                "shift_symbol": "alternate_shift",
            },
            "golden_vectors": {
                "format": "json_v1",
                "path": "golden_vectors/vectors.json",
            },
            "io_alignment": 32,
        }
        (package / "model.json").write_text(json.dumps(manifest))
        return package

    def test_alternate_tensor_contract_is_not_hardcoded(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            model = load_model_package(self.make_package(Path(temporary_directory)))

        self.assertEqual((1, 64), model.input.shape)
        self.assertEqual(64, model.input.size_bytes)
        self.assertEqual("int16", model.output.dtype)
        self.assertEqual(8, model.output.size_bytes)
        self.assertEqual(32, model.io_alignment)

    def test_archive_change_invalidates_model_identity(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            package = self.make_package(Path(temporary_directory))
            (package / "artifacts" / "alternate.a").write_bytes(b"changed archive")
            with self.assertRaisesRegex(ModelPackageError, "library SHA-256"):
                load_model_package(package)

    def test_declared_tensor_size_must_match_shape_and_dtype(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            package = self.make_package(Path(temporary_directory))
            manifest_path = package / "model.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["output"]["size_bytes"] = 4
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ModelPackageError, "calculated 8"):
                load_model_package(package)

    def test_output_and_metrics_must_fit_protocol_length(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            package = self.make_package(Path(temporary_directory))
            manifest_path = package / "model.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["output"] = {
                "shape": [65516],
                "dtype": "uint8",
                "size_bytes": 65516,
                "runtime_field": "scores",
            }
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ModelPackageError, "plus 20-byte metrics"):
                load_model_package(package)

    def test_identity_float32_preprocessing_requires_float_input(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            package = self.make_package(Path(temporary_directory))
            manifest_path = package / "model.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["preprocessing"] = {"type": "identity_float32_le"}
            with self.assertRaisesRegex(ModelPackageError, "requires float32 input"):
                manifest_path.write_text(json.dumps(manifest))
                load_model_package(package)

            manifest["input"]["dtype"] = "float32"
            manifest["input"]["size_bytes"] = 256
            manifest_path.write_text(json.dumps(manifest))
            model = load_model_package(package)
            self.assertEqual("identity_float32_le", model.preprocessing["type"])
            self.assertEqual(256, model.input.size_bytes)

    def test_adapter_is_generated_from_runtime_contract(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            package = self.make_package(root)
            model = load_model_package(package)
            source = render_adapter(model)
            output = root / "build" / "model_adapter.c"
            generated_model = generate_adapter(package, output)

            self.assertEqual("alternate_classifier", generated_model.name)
            self.assertEqual(source, output.read_text())
            self.assertIn("struct alternate_inputs inputs", source)
            self.assertIn(".sensor_input = input", source)
            self.assertIn("struct alternate_outputs outputs", source)
            self.assertIn(".scores = output", source)
            self.assertIn("return alternate_run(&inputs, &outputs);", source)
            self.assertIn("alternate_finished = 0;", source)
            self.assertIn("alternate_continue();", source)

    def test_runtime_contract_rejects_invalid_or_missing_declarations(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            package = self.make_package(Path(temporary_directory))
            manifest_path = package / "model.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["runtime"]["input_struct"] = "not-a-c-identifier"
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ModelPackageError, "runtime.input_struct"):
                load_model_package(package)

            manifest["runtime"]["input_struct"] = "missing_inputs"
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ModelPackageError, "does not declare runtime token"):
                load_model_package(package)


if __name__ == "__main__":
    unittest.main()
