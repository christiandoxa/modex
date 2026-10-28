"""Local source-cache integrity checks for the CI reference helper."""

from pathlib import Path
import hashlib
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.ci.reference import (
    BASELINE,
    acquire_oracle,
    metadata_for,
    reference_for,
    verify_cached_source,
    verify_tag,
)


class CachedSourceIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="modex-reference-test-")
        self.addCleanup(self.temporary.cleanup)
        self.checkout = Path(self.temporary.name) / "source"
        self.checkout.mkdir()
        subprocess.run(["git", "init", "--quiet", str(self.checkout)], check=True)
        subprocess.run(["git", "-C", str(self.checkout), "config", "user.name", "Modex CI test"], check=True)
        subprocess.run(["git", "-C", str(self.checkout), "config", "user.email", "ci@example.invalid"], check=True)
        (self.checkout / "tracked.txt").write_text("frozen source\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.checkout), "add", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(self.checkout), "commit", "--quiet", "-m", "fixture"], check=True)
        self.commit = subprocess.check_output(
            ["git", "-C", str(self.checkout), "rev-parse", "HEAD"], text=True,
        ).strip()

    def test_clean_source_matches_its_frozen_tree(self):
        verify_cached_source(self.checkout, self.commit)

    def test_tampered_tracked_file_is_rejected_even_when_git_skips_its_stat(self):
        subprocess.run(["git", "-C", str(self.checkout), "update-index", "--assume-unchanged", "tracked.txt"], check=True)
        (self.checkout / "tracked.txt").write_text("changed implementation\n", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "modified tracked content"):
            verify_cached_source(self.checkout, self.commit)

    def test_untracked_files_are_rejected(self):
        (self.checkout / "untracked.py").write_text("print('changed behavior')\n", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "dirty or contains untracked"):
            verify_cached_source(self.checkout, self.commit)

    def test_active_and_historical_tags_resolve_to_their_frozen_references(self):
        self.assertIs(reference_for("active"), BASELINE["reference"])
        self.assertIs(reference_for(BASELINE["reference"]["tag"]), BASELINE["reference"])
        self.assertEqual(reference_for("0.439.2")["commit"], "72b77478a5198fc5da6b4d2253137f9cdbf43be9")
        self.assertEqual(reference_for("0.439.5")["commit"], "ac9aad08f25d6dc8cda96463ce2045b40f35f510")
        self.assertEqual(reference_for("previous")["tag"], "0.439.1")

    def test_previous_release_uses_recorded_historical_asset_checksums(self):
        _, _, oracle_sha, manifest_sha = metadata_for(reference_for("previous"))
        self.assertEqual(oracle_sha, "b4511d679dd6da53f706400dba5b368ffc5b5663f8764fa0c8f148b358b9255a")
        self.assertEqual(manifest_sha, "f5f4269d90de95c1cde06043df21c00a253681fcc96a8589cae067beb2fb95d9")

    def test_prodex_oracle_override_only_applies_to_the_active_reference(self):
        cache = Path(self.temporary.name) / "cache"
        historical = cache / "oracles/0.439.5/prodex"
        historical.parent.mkdir(parents=True)
        historical.write_bytes(b"historical oracle")
        configured = Path(self.temporary.name) / "active-oracle"
        configured.write_bytes(b"active oracle")
        historical_sha = hashlib.sha256(historical.read_bytes()).hexdigest()
        active_sha = hashlib.sha256(configured.read_bytes()).hexdigest()
        historical_reference = {"tag": "0.439.5", "oracle": "prodex"}
        active_reference = {"tag": "0.439.2", "oracle": "prodex"}
        with patch.dict(os.environ, {"MODEX_REFERENCE_CACHE": str(cache), "PRODEX_ORACLE": str(configured)}):
            with patch("scripts.ci.reference.metadata_for", return_value=(Path("evidence"), "prodex", historical_sha, "0" * 64)):
                self.assertEqual(acquire_oracle(historical_reference), historical.resolve())
            with patch("scripts.ci.reference.metadata_for", return_value=(Path("evidence"), "prodex", active_sha, "0" * 64)):
                self.assertEqual(acquire_oracle(active_reference, active=True), configured.resolve())


class FrozenTagVerificationTests(unittest.TestCase):
    def test_missing_official_tag_is_distinguished_from_a_moved_tag(self):
        reference = reference_for("0.439.2")
        missing = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with patch("scripts.ci.reference.subprocess.run", return_value=missing):
            with self.assertRaisesRegex(
                SystemExit,
                r"official Prodex tag 0\.439\.2 is missing; expected frozen commit "
                r"72b77478a5198fc5da6b4d2253137f9cdbf43be9.*refusing to substitute",
            ):
                verify_tag(reference)

    def test_moved_official_tag_reports_the_resolved_commit(self):
        reference = reference_for("0.439.2")
        moved = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\trefs/tags/0.439.2\n",
            stderr="",
        )
        with patch("scripts.ci.reference.subprocess.run", return_value=moved):
            with self.assertRaisesRegex(
                SystemExit,
                r"official tag 0\.439\.2 resolves to 'a{40}', expected frozen commit "
                r"72b77478a5198fc5da6b4d2253137f9cdbf43be9",
            ):
                verify_tag(reference)

    def test_remote_lookup_failure_is_reported_as_a_verification_error(self):
        reference = reference_for("0.439.2")
        failure = subprocess.CalledProcessError(
            128, ["git", "ls-remote"], stderr="fatal: could not resolve host\n"
        )
        with patch("scripts.ci.reference.subprocess.run", side_effect=failure):
            with self.assertRaisesRegex(
                SystemExit, r"could not verify official Prodex tag 0\.439\.2: fatal: could not resolve host"
            ):
                verify_tag(reference)

    def test_missing_previous_release_tag_is_reported_without_fallback(self):
        reference = reference_for("0.439.1")
        missing = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with patch("scripts.ci.reference.subprocess.run", return_value=missing):
            with self.assertRaisesRegex(SystemExit, r"official Prodex tag 0\.439\.1 is missing"):
                verify_tag(reference)


if __name__ == "__main__":
    unittest.main()
