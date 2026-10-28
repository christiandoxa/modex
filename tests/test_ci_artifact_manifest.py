"""Isolated integrity tests for cross-job native build artifact manifests."""

import copy
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "scripts/ci/artifact-manifest.py"
SPEC = importlib.util.spec_from_file_location("modex_ci_artifact_manifest", MANIFEST_PATH)
MANIFEST = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MANIFEST)
COMPILER_VERSION = "Mojo 1.2.0 (synthetic test toolchain)"
RUNTIME_VERSION = "Python 3.14.10 (synthetic test runtime)"
BUILD_FLAGS = ["-O3", "--target-cpu=x86-64-v3", "-I", "src"]


class ArtifactManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="modex-artifact-manifest-")
        self.base = Path(self.temp.name)
        self.root = self.base / "artifact"
        self.root.mkdir()
        self.toolchain = self.base / "toolchain"
        self.compiler = self.toolchain / "bin" / "mojo"
        self.compiler.parent.mkdir(parents=True)
        self.compiler.write_text(
            f"#!/bin/sh\nprintf '%s\\n' '{COMPILER_VERSION}'\n", encoding="utf-8"
        )
        self.compiler.chmod(0o755)
        self.runtime = self.toolchain / "bin" / "python"
        self.runtime.write_text(
            f"#!/bin/sh\nprintf '%s\\n' '{RUNTIME_VERSION}'\n", encoding="utf-8"
        )
        self.runtime.chmod(0o755)
        self.stdlib = {}
        for name in ("modular", "mojo"):
            package = self.toolchain / "lib" / name
            package.mkdir(parents=True)
            (package / "stdlib.mojoc").write_bytes(f"{name} standard library".encode())
            (package / "stdlib.mojoc").chmod(0o644)
            self.stdlib[name] = package
        self.artifact = self.root / "bin" / "driver"
        self.artifact.parent.mkdir()
        self.artifact.write_bytes(b"synthetic native test executable")
        self.artifact.chmod(0o755)
        self.paths = ["bin/driver"]
        self.manifest_path = "manifest.json"
        self.identity = MANIFEST._identity(
            "a" * 40,
            "12345",
            2,
            "unit-linux",
            "x86_64-linux-gnu",
            "x86-64-v3",
            BUILD_FLAGS,
            COMPILER_VERSION,
            self.compiler,
            RUNTIME_VERSION,
            self.runtime,
            "1.2.0",
            self.stdlib,
        )

    def tearDown(self):
        self.temp.cleanup()

    def create(self):
        return MANIFEST.create_manifest(
            self.root, self.manifest_path, self.identity, self.paths
        )

    def verify(self, digest, identity=None, paths=None):
        return MANIFEST.verify_manifest(
            self.root,
            self.manifest_path,
            digest,
            self.identity if identity is None else identity,
            self.paths if paths is None else paths,
        )

    def test_valid_same_run_manifest_verifies_and_is_read_only(self):
        digest = self.create()

        self.assertEqual(len(digest), 64)
        self.assertEqual(self.verify(digest), digest)
        self.assertEqual(self.artifact.stat().st_mode & 0o777, 0o755)
        self.assertEqual((self.root / self.manifest_path).stat().st_mode & 0o777, 0o444)

    def test_artifact_byte_tampering_fails(self):
        digest = self.create()
        self.artifact.write_bytes(b"tampered executable")

        with self.assertRaisesRegex(MANIFEST.ManifestError, "content, mode or size mismatch"):
            self.verify(digest)

    def test_manifest_tampering_fails_against_trusted_digest(self):
        digest = self.create()
        manifest = self.root / self.manifest_path
        manifest.chmod(0o644)
        document = json.loads(manifest.read_text(encoding="utf-8"))
        document["identity"]["target"] = "aarch64-linux-gnu"
        manifest.write_bytes(MANIFEST._canonical_json(document))
        manifest.chmod(0o444)

        with self.assertRaisesRegex(MANIFEST.ManifestError, "trusted expected digest"):
            self.verify(digest)

    def test_wrong_source_revision_run_or_target_fails(self):
        digest = self.create()
        alternatives = []
        wrong_revision = copy.deepcopy(self.identity)
        wrong_revision["source_commit"] = "b" * 40
        alternatives.append(wrong_revision)
        wrong_run = copy.deepcopy(self.identity)
        wrong_run["producer"]["run_id"] = "54321"
        alternatives.append(wrong_run)
        wrong_attempt = copy.deepcopy(self.identity)
        wrong_attempt["producer"]["run_attempt"] = 3
        alternatives.append(wrong_attempt)
        wrong_target = copy.deepcopy(self.identity)
        wrong_target["target"] = "aarch64-linux-gnu"
        alternatives.append(wrong_target)
        wrong_cpu = copy.deepcopy(self.identity)
        wrong_cpu["build"]["target_cpu"] = "x86-64-v4"
        alternatives.append(wrong_cpu)
        wrong_job = copy.deepcopy(self.identity)
        wrong_job["producer"]["job"] = "other-linux"
        alternatives.append(wrong_job)

        for identity in alternatives:
            with self.subTest(identity=identity):
                with self.assertRaisesRegex(MANIFEST.ManifestError, "identity mismatch"):
                    self.verify(digest, identity=identity)

    def test_wrong_compiler_runtime_or_standard_library_identity_fails(self):
        digest = self.create()
        wrong_compiler = copy.deepcopy(self.identity)
        wrong_compiler["compiler"]["sha256"] = "0" * 64
        wrong_stdlib = copy.deepcopy(self.identity)
        wrong_stdlib["stdlib"]["sha256"] = "1" * 64
        wrong_runtime = copy.deepcopy(self.identity)
        wrong_runtime["runtime"]["sha256"] = "2" * 64

        for identity in (wrong_compiler, wrong_runtime, wrong_stdlib):
            with self.subTest(identity=identity):
                with self.assertRaisesRegex(MANIFEST.ManifestError, "identity mismatch"):
                    self.verify(digest, identity=identity)

    def test_build_flags_and_target_cpu_are_verified_and_consistent(self):
        digest = self.create()
        wrong_flags = copy.deepcopy(self.identity)
        wrong_flags["build"]["flags"][0] = "-O0"
        with self.assertRaisesRegex(MANIFEST.ManifestError, "identity mismatch"):
            self.verify(digest, identity=wrong_flags)

        with self.assertRaisesRegex(MANIFEST.ManifestError, "matching target CPU"):
            MANIFEST._identity(
                "a" * 40, "12345", 2, "unit-linux", "x86_64-linux-gnu", "x86-64-v4",
                BUILD_FLAGS, COMPILER_VERSION, self.compiler, RUNTIME_VERSION, self.runtime,
                "1.2.0", self.stdlib,
            )

    def test_reported_compiler_version_must_match_binary_output(self):
        with self.assertRaisesRegex(MANIFEST.ManifestError, "compiler version mismatch"):
            MANIFEST._identity(
                "a" * 40, "12345", 2, "unit-linux", "x86_64-linux-gnu", "x86-64-v3",
                BUILD_FLAGS, "Mojo 9.9.9", self.compiler, RUNTIME_VERSION, self.runtime,
                "1.2.0", self.stdlib,
            )

    def test_reported_runtime_version_must_match_runtime_output(self):
        with self.assertRaisesRegex(MANIFEST.ManifestError, "runtime version mismatch"):
            MANIFEST._identity(
                "a" * 40, "12345", 2, "unit-linux", "x86_64-linux-gnu", "x86-64-v3",
                BUILD_FLAGS, COMPILER_VERSION, self.compiler, "Python 9.9.9", self.runtime,
                "1.2.0", self.stdlib,
            )

    def test_runtime_must_be_executable_and_not_symlinked(self):
        self.runtime.chmod(0o644)
        with self.assertRaisesRegex(MANIFEST.ManifestError, "not executable"):
            MANIFEST._identity(
                "a" * 40, "12345", 2, "unit-linux", "x86_64-linux-gnu", "x86-64-v3",
                BUILD_FLAGS, COMPILER_VERSION, self.compiler, RUNTIME_VERSION, self.runtime,
                "1.2.0", self.stdlib,
            )
        self.runtime.chmod(0o755)
        real_runtime = self.runtime.with_name("python-real")
        self.runtime.rename(real_runtime)
        self.runtime.symlink_to(real_runtime)
        with self.assertRaisesRegex(MANIFEST.ManifestError, "cannot safely traverse runtime path"):
            MANIFEST._identity(
                "a" * 40, "12345", 2, "unit-linux", "x86_64-linux-gnu", "x86-64-v3",
                BUILD_FLAGS, COMPILER_VERSION, self.compiler, RUNTIME_VERSION, self.runtime,
                "1.2.0", self.stdlib,
            )

    def test_symlinked_artifact_is_rejected(self):
        digest = self.create()
        outside = self.base / "outside"
        outside.write_bytes(b"outside artifact")
        self.artifact.unlink()
        self.artifact.symlink_to(outside)

        with self.assertRaises(MANIFEST.ManifestError):
            self.verify(digest)

    def test_symlinked_compiler_and_standard_library_files_are_rejected(self):
        compiler_copy = self.compiler.with_name("mojo-real")
        self.compiler.rename(compiler_copy)
        self.compiler.symlink_to(compiler_copy)
        with self.assertRaisesRegex(MANIFEST.ManifestError, "cannot safely traverse compiler path"):
            MANIFEST._identity(
                "a" * 40, "12345", 2, "unit-linux", "x86_64-linux-gnu", "x86-64-v3",
                BUILD_FLAGS, COMPILER_VERSION, self.compiler, RUNTIME_VERSION, self.runtime,
                "1.2.0", self.stdlib,
            )
        self.compiler.unlink()
        compiler_copy.rename(self.compiler)
        outside = self.base / "outside-stdlib"
        outside.write_bytes(b"outside standard library")
        (self.stdlib["mojo"] / "escape.mojoc").symlink_to(outside)
        with self.assertRaisesRegex(MANIFEST.ManifestError, "symlink or special file"):
            MANIFEST._identity(
                "a" * 40, "12345", 2, "unit-linux", "x86_64-linux-gnu", "x86-64-v3",
                BUILD_FLAGS, COMPILER_VERSION, self.compiler, RUNTIME_VERSION, self.runtime,
                "1.2.0", self.stdlib,
            )

    def test_symlinked_ancestor_directories_are_rejected(self):
        linked_toolchain = self.base / "toolchain-link"
        linked_toolchain.symlink_to(self.toolchain, target_is_directory=True)
        linked_compiler = linked_toolchain / "bin" / "mojo"
        with self.assertRaisesRegex(MANIFEST.ManifestError, "cannot safely traverse compiler path"):
            MANIFEST._identity(
                "a" * 40, "12345", 2, "unit-linux", "x86_64-linux-gnu", "x86-64-v3",
                BUILD_FLAGS, COMPILER_VERSION, linked_compiler, RUNTIME_VERSION, self.runtime,
                "1.2.0", self.stdlib,
            )

        linked_roots = {
            name: linked_toolchain / "lib" / name for name in ("modular", "mojo")
        }
        with self.assertRaisesRegex(MANIFEST.ManifestError, "cannot safely traverse stdlib modular"):
            MANIFEST._identity(
                "a" * 40, "12345", 2, "unit-linux", "x86_64-linux-gnu", "x86-64-v3",
                BUILD_FLAGS, COMPILER_VERSION, self.compiler, RUNTIME_VERSION, self.runtime,
                "1.2.0", linked_roots,
            )

    def test_symlinked_parent_and_manifest_path_traversal_are_rejected(self):
        digest = self.create()
        outside = self.base / "outside-directory"
        outside.mkdir()
        (outside / "driver").write_bytes(b"outside artifact")
        (self.root / "bin").rename(self.root / "bin-real")
        (self.root / "bin").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(MANIFEST.ManifestError):
            self.verify(digest)

        with self.assertRaisesRegex(MANIFEST.ManifestError, "normalized and relative"):
            MANIFEST.create_manifest(
                self.root, "manifest.json", self.identity, ["../outside"]
            )

    def test_manifest_with_traversal_path_is_rejected_even_with_new_digest(self):
        self.create()
        manifest = self.root / self.manifest_path
        document = json.loads(manifest.read_text(encoding="utf-8"))
        document["files"][0]["path"] = "../outside"
        content = MANIFEST._canonical_json(document)
        manifest.chmod(0o644)
        manifest.write_bytes(content)
        manifest.chmod(0o444)
        digest = hashlib.sha256(content).hexdigest()

        with self.assertRaisesRegex(MANIFEST.ManifestError, "normalized and relative"):
            self.verify(digest)

    def test_permission_changes_and_missing_files_are_rejected(self):
        digest = self.create()
        self.artifact.chmod(0o700)
        with self.assertRaisesRegex(MANIFEST.ManifestError, "content, mode or size mismatch"):
            self.verify(digest)

        self.artifact.unlink()
        with self.assertRaises(MANIFEST.ManifestError):
            self.verify(digest)

    def test_create_requires_every_listed_file_and_rejects_overwrite(self):
        with self.assertRaises(MANIFEST.ManifestError):
            MANIFEST.create_manifest(
                self.root, self.manifest_path, self.identity, ["bin/missing"]
            )

        self.create()
        with self.assertRaisesRegex(MANIFEST.ManifestError, "cannot create immutable manifest"):
            self.create()

    def test_expected_artifact_inventory_must_match(self):
        digest = self.create()

        with self.assertRaisesRegex(MANIFEST.ManifestError, "expected file inventory"):
            self.verify(digest, paths=["bin/other"])

    def test_cli_creates_digest_for_trusted_job_output_and_verifies_with_it(self):
        args = [
            "--root", str(self.root), "--manifest", self.manifest_path,
            "--file", self.paths[0], "--source-commit", "a" * 40,
            "--run-id", "12345", "--run-attempt", "2", "--producer-job", "unit-linux",
            "--target", "x86_64-linux-gnu", "--target-cpu", "x86-64-v3",
            "--compiler", str(self.compiler),
            "--expected-compiler-version", COMPILER_VERSION,
            "--runtime", str(self.runtime),
            "--expected-runtime-version", RUNTIME_VERSION,
            "--stdlib-version", "1.2.0", "--stdlib", f"modular={self.stdlib['modular']}",
            "--stdlib", f"mojo={self.stdlib['mojo']}",
        ]
        for flag in BUILD_FLAGS:
            args.append(f"--build-flag={flag}")
        digest_output = io.StringIO()
        with contextlib.redirect_stdout(digest_output):
            self.assertEqual(MANIFEST.main(["create", *args]), 0)
        digest = digest_output.getvalue().strip()
        self.assertEqual(len(digest), 64)

        verify_output = io.StringIO()
        with contextlib.redirect_stdout(verify_output):
            self.assertEqual(MANIFEST.main([
                "verify", *args, "--expected-manifest-sha256", digest,
            ]), 0)
        self.assertIn(f"VERIFIED {digest}", verify_output.getvalue())

    def _bundle(self):
        source = self.base / "bundle-source"
        source.mkdir()
        binary = source / "modex"
        binary.write_bytes(b"synthetic Modex executable")
        binary.chmod(0o755)
        manifest_digest = MANIFEST.create_manifest(
            source, "manifest.json", self.identity, ["modex"]
        )
        bundle = self.base / "modex-build.tar"
        with tarfile.open(bundle, "w") as archive:
            for name in ("manifest.json", "modex"):
                archive.add(source / name, arcname=name, recursive=False)
        return source, bundle, manifest_digest

    def test_verified_bundle_extracts_only_the_executable_and_manifest(self):
        _, bundle, manifest_digest = self._bundle()
        destination = self.base / "extracted"
        destination.mkdir()
        bundle_digest = hashlib.sha256(bundle.read_bytes()).hexdigest()

        extract_output = io.StringIO()
        with contextlib.redirect_stdout(extract_output):
            self.assertEqual(MANIFEST.main([
                "extract", "--bundle", str(bundle), "--destination", str(destination),
                "--expected-bundle-sha256", bundle_digest,
            ]), 0)

        self.assertIn(str(bundle), extract_output.getvalue())
        self.assertEqual(sorted(path.name for path in destination.iterdir()), ["manifest.json", "modex"])
        self.assertEqual((destination / "modex").stat().st_mode & 0o777, 0o755)
        self.assertEqual((destination / "manifest.json").stat().st_mode & 0o777, 0o444)
        self.assertEqual(
            MANIFEST.verify_manifest(destination, "manifest.json", manifest_digest, self.identity, ["modex"]),
            manifest_digest,
        )

    def test_bundle_digest_mismatch_fails_before_extraction(self):
        _, bundle, _ = self._bundle()
        expected = hashlib.sha256(bundle.read_bytes()).hexdigest()
        bundle.write_bytes(bundle.read_bytes() + b"tamper")
        destination = self.base / "extracted"
        destination.mkdir()

        with self.assertRaisesRegex(MANIFEST.ManifestError, "trusted expected digest"):
            MANIFEST.extract_bundle(bundle, destination, expected)
        self.assertEqual(list(destination.iterdir()), [])

    def test_bundle_rejects_nonempty_destination_without_overwriting(self):
        _, bundle, _ = self._bundle()
        digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
        destination = self.base / "existing"
        destination.mkdir()
        marker = destination / "preserve"
        marker.write_bytes(b"existing content")

        with self.assertRaisesRegex(MANIFEST.ManifestError, "must be empty"):
            MANIFEST.extract_bundle(bundle, destination, digest)

        self.assertEqual([path.name for path in destination.iterdir()], ["preserve"])
        self.assertEqual(marker.read_bytes(), b"existing content")

    def test_bundle_rejects_traversal_and_nonregular_entries(self):
        source, _, _ = self._bundle()
        for entry_name, entry_type, mode in (
            ("../outside", tarfile.REGTYPE, 0o755),
            ("modex", tarfile.SYMTYPE, 0o755),
            ("modex", tarfile.REGTYPE, 0o644),
        ):
            with self.subTest(entry_name=entry_name, entry_type=entry_type):
                bundle = self.base / f"bad-{len(list(self.base.iterdir()))}.tar"
                with tarfile.open(bundle, "w") as archive:
                    archive.add(source / "manifest.json", arcname="manifest.json", recursive=False)
                    info = tarfile.TarInfo(entry_name)
                    info.mode = mode
                    info.type = entry_type
                    if entry_type == tarfile.SYMTYPE:
                        info.linkname = "../../outside"
                        archive.addfile(info)
                    else:
                        payload = b"outside bytes"
                        info.size = len(payload)
                        archive.addfile(info, io.BytesIO(payload))
                digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
                destination = self.base / f"extract-{len(list(self.base.iterdir()))}"
                destination.mkdir()
                with self.assertRaises(MANIFEST.ManifestError):
                    MANIFEST.extract_bundle(bundle, destination, digest)
                self.assertEqual(list(destination.iterdir()), [])
                self.assertFalse((self.base / "outside").exists())


if __name__ == "__main__":
    unittest.main()
