"""Local source-cache integrity checks for the CI reference helper."""

from pathlib import Path
import hashlib
import os
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.ci.reference import (
    BASELINE,
    acquire_oracle,
    acquire_source,
    metadata_for,
    reference_for,
    verify_cached_source,
    verify_tag,
)


class CachedSourceIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="modex-reference-test-")
        self.addCleanup(self.temporary.cleanup)
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": self.temporary.name,
            "XDG_CONFIG_HOME": self.temporary.name,
            "XDG_CACHE_HOME": self.temporary.name,
            "XDG_DATA_HOME": self.temporary.name,
            "TMPDIR": self.temporary.name,
            "LANG": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
        }
        self.environment_patch = patch.dict(os.environ, environment, clear=True)
        self.environment_patch.start()
        self.addCleanup(self.environment_patch.stop)
        self.checkout = Path(self.temporary.name) / "source"
        self.checkout.mkdir()
        subprocess.run(["git", "init", "--quiet", "--template=", str(self.checkout)], check=True)
        subprocess.run(["git", "-C", str(self.checkout), "config", "user.name", "Modex CI test"], check=True)
        subprocess.run(["git", "-C", str(self.checkout), "config", "user.email", "ci@example.invalid"], check=True)
        (self.checkout / "tracked.txt").write_text("frozen source\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.checkout), "add", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(self.checkout), "commit", "--quiet", "-m", "fixture"], check=True)
        self.commit = subprocess.check_output(
            ["git", "-C", str(self.checkout), "rev-parse", "HEAD"], text=True,
        ).strip()

    def _write_sentinel_command(self, name):
        marker = Path(self.temporary.name) / f"{name}.ran"
        command = Path(self.temporary.name) / name
        command.write_text(
            f"#!/bin/sh\nprintf ran > {shlex.quote(str(marker))}\n"
            + ("cat\n" if name == "clean-filter" else "printf 'token\\0'\n"),
            encoding="utf-8",
        )
        command.chmod(0o755)
        return command, marker

    def _commit_fixture(self, message="fixture"):
        subprocess.run(["git", "-C", str(self.checkout), "add", "--all"], check=True)
        subprocess.run(["git", "-C", str(self.checkout), "commit", "--quiet", "-m", message], check=True)
        self.commit = subprocess.check_output(
            ["git", "-C", str(self.checkout), "rev-parse", "HEAD"], text=True,
        ).strip()

    def test_clean_source_matches_its_frozen_tree(self):
        verify_cached_source(self.checkout, self.commit)

    def test_tampered_tracked_file_is_rejected_despite_index_assume_unchanged(self):
        subprocess.run(["git", "-C", str(self.checkout), "update-index", "--assume-unchanged", "tracked.txt"], check=True)
        (self.checkout / "tracked.txt").write_text("changed implementation\n", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "modified tracked content"):
            verify_cached_source(self.checkout, self.commit)

    def test_untracked_files_are_rejected(self):
        (self.checkout / "untracked.py").write_text("print('changed behavior')\n", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "dirty or contains untracked"):
            verify_cached_source(self.checkout, self.commit)

    def test_tracked_directory_symlink_is_verified_without_traversing_it(self):
        payload = Path(self.temporary.name) / "payload"
        payload.mkdir()
        (payload / "outside.txt").write_text("outside source\n", encoding="utf-8")
        (self.checkout / "payload-link").symlink_to("../payload", target_is_directory=True)
        self._commit_fixture()

        verify_cached_source(self.checkout, self.commit)

    def test_changed_tracked_directory_symlink_target_is_rejected(self):
        for name in ("original", "replacement"):
            directory = self.checkout / name
            directory.mkdir()
            (directory / "tracked.txt").write_text(f"{name}\n", encoding="utf-8")
        link = self.checkout / "payload-link"
        link.symlink_to("original", target_is_directory=True)
        self._commit_fixture()
        link.unlink()
        link.symlink_to("replacement", target_is_directory=True)

        with self.assertRaisesRegex(SystemExit, "modified tracked content"):
            verify_cached_source(self.checkout, self.commit)

    def test_untracked_directory_symlink_is_rejected(self):
        target = Path(self.temporary.name) / "outside"
        target.mkdir()
        (target / "not-tracked.txt").write_text("outside source\n", encoding="utf-8")
        (self.checkout / "untracked-link").symlink_to(target, target_is_directory=True)

        with self.assertRaisesRegex(SystemExit, "dirty or contains untracked"):
            verify_cached_source(self.checkout, self.commit)

    def test_replaced_tracked_parent_directory_is_rejected(self):
        parent = self.checkout / "nested"
        parent.mkdir()
        (parent / "tracked.txt").write_text("frozen parent\n", encoding="utf-8")
        self._commit_fixture()
        replacement = Path(self.temporary.name) / "replacement"
        replacement.mkdir()
        (replacement / "tracked.txt").write_text("frozen parent\n", encoding="utf-8")
        parent.rename(Path(self.temporary.name) / "original-parent")
        parent.symlink_to(replacement, target_is_directory=True)

        with self.assertRaises(SystemExit):
            verify_cached_source(self.checkout, self.commit)

    def test_source_fetch_must_resolve_to_the_pinned_commit(self):
        (self.checkout / "tracked.txt").write_text("different fetched source\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.checkout), "add", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(self.checkout), "commit", "--quiet", "-m", "different source"], check=True)
        wrong_commit = subprocess.check_output(
            ["git", "-C", str(self.checkout), "rev-parse", "HEAD"], text=True,
        ).strip()
        reference = {"repository": str(self.checkout), "tag": "synthetic", "commit": self.commit}
        original_run = subprocess.run

        def wrong_fetch(command, *args, **kwargs):
            command = list(command)
            if "fetch" in command:
                command[-1] = wrong_commit
            return original_run(command, *args, **kwargs)

        cache = Path(self.temporary.name) / "cache"
        with patch.dict(os.environ, {"MODEX_REFERENCE_CACHE": str(cache)}):
            with patch("scripts.ci.reference.reference_for", return_value=reference):
                with patch("scripts.ci.reference.metadata_for", return_value=(Path("evidence"), "prodex", "0" * 64, "0" * 64)):
                    with patch("scripts.ci.reference.verify_tag"):
                        with patch("scripts.ci.reference.subprocess.run", side_effect=wrong_fetch):
                            with self.assertRaisesRegex(SystemExit, r"source checkout resolved to .* expected"):
                                acquire_source("active")

    def _assert_source_fallback_not_used(self, error):
        reference = {"repository": "https://github.com/christiandoxa/prodex", "tag": "synthetic", "commit": self.commit}
        with patch.dict(os.environ, {"MODEX_REFERENCE_CACHE": str(Path(self.temporary.name) / "cache")}):
            with patch("scripts.ci.reference.reference_for", return_value=reference):
                with patch("scripts.ci.reference.metadata_for", return_value=(Path("evidence"), "prodex", "0" * 64, "0" * 64)):
                    with patch("scripts.ci.reference.verify_tag", side_effect=SystemExit(error)):
                        with patch("scripts.ci.reference.download") as download:
                            with patch("scripts.ci.reference.urlopen") as urlopen:
                                with patch("scripts.ci.reference.subprocess.run") as run:
                                    with self.assertRaises(SystemExit):
                                        acquire_source("active")
        download.assert_not_called()
        urlopen.assert_not_called()
        run.assert_not_called()

    def test_moved_tag_does_not_use_the_source_fallback(self):
        self._assert_source_fallback_not_used("official tag moved from the frozen commit")

    def test_remote_failure_does_not_use_the_source_fallback(self):
        self._assert_source_fallback_not_used("could not verify official Prodex tag: network failure")

    def test_replace_ref_cannot_substitute_the_frozen_tree(self):
        (self.checkout / "tracked.txt").write_text("replacement implementation\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.checkout), "add", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(self.checkout), "commit", "--quiet", "-m", "replacement"], check=True)
        replacement = subprocess.check_output(
            ["git", "-C", str(self.checkout), "rev-parse", "HEAD"], text=True,
        ).strip()
        subprocess.run(["git", "-C", str(self.checkout), "replace", self.commit, replacement], check=True)
        subprocess.run(["git", "-C", str(self.checkout), "checkout", "--quiet", "--detach", self.commit], check=True)
        self.assertEqual(
            subprocess.check_output(["git", "-C", str(self.checkout), "rev-parse", "HEAD"], text=True).strip(),
            self.commit,
        )
        self.assertEqual((self.checkout / "tracked.txt").read_text(encoding="utf-8"), "replacement implementation\n")

        with self.assertRaises(SystemExit):
            verify_cached_source(self.checkout, self.commit)

    def test_cached_fsmonitor_command_is_not_executed(self):
        command, marker = self._write_sentinel_command("fsmonitor")
        subprocess.run(["git", "-C", str(self.checkout), "config", "core.fsmonitor", str(command)], check=True)

        try:
            verify_cached_source(self.checkout, self.commit)
        except SystemExit:
            pass
        self.assertFalse(marker.exists(), "cached core.fsmonitor command ran during source verification")

    def test_cached_clean_filter_command_is_not_executed(self):
        (self.checkout / ".gitattributes").write_text("tracked.txt filter=sentinel\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.checkout), "add", ".gitattributes"], check=True)
        subprocess.run(["git", "-C", str(self.checkout), "commit", "--quiet", "-m", "filter attribute"], check=True)
        self.commit = subprocess.check_output(
            ["git", "-C", str(self.checkout), "rev-parse", "HEAD"], text=True,
        ).strip()
        command, marker = self._write_sentinel_command("clean-filter")
        subprocess.run(
            ["git", "-C", str(self.checkout), "config", "filter.sentinel.clean", f"{shlex.quote(str(command))} %f"],
            check=True,
        )
        path = self.checkout / "tracked.txt"
        info = path.stat()
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns + 2_000_000_000))

        try:
            verify_cached_source(self.checkout, self.commit)
        except SystemExit:
            pass
        self.assertFalse(marker.exists(), "cached clean filter command ran during source verification")

    def test_active_and_historical_tags_resolve_to_their_frozen_references(self):
        self.assertIs(reference_for("active"), BASELINE["reference"])
        self.assertIs(reference_for(BASELINE["reference"]["tag"]), BASELINE["reference"])
        self.assertEqual(reference_for("active")["tag"], "0.166.0")
        self.assertEqual(reference_for("active")["commit"], "9f69e1835808f478f59f12a3ae3fa88027d896a4")
        self.assertEqual(reference_for("0.439.2")["commit"], "72b77478a5198fc5da6b4d2253137f9cdbf43be9")
        self.assertEqual(reference_for("0.439.5")["commit"], "ac9aad08f25d6dc8cda96463ce2045b40f35f510")
        self.assertEqual(reference_for("0.165.1")["commit"], "10ae15b5d1806302b60f051e4e6fec788044f4c2")
        self.assertEqual(reference_for("previous")["tag"], "0.165.1")
        self.assertEqual(reference_for("0.439.1")["commit"], "81c1a01933bc33f536a24452c3fd72c3f8d0b1f3")

    def test_uncached_oracle_is_not_replaced_when_the_official_release_is_missing(self):
        cache = Path(self.temporary.name) / "cache"
        reference = reference_for("active")
        missing = f"official Prodex tag {reference['tag']} is missing"
        with patch.dict(os.environ, {"MODEX_REFERENCE_CACHE": str(cache), "PRODEX_ORACLE": ""}):
            with patch("scripts.ci.reference.verify_tag", side_effect=SystemExit(missing)):
                with patch("scripts.ci.reference.download") as download:
                    with patch("scripts.ci.reference.urlopen", side_effect=AssertionError("network fallback attempted")) as urlopen:
                        with patch("scripts.ci.reference.subprocess.run") as run:
                            with self.assertRaisesRegex(SystemExit, "is missing"):
                                acquire_oracle(reference, active=True)
        download.assert_not_called()
        urlopen.assert_not_called()
        run.assert_not_called()
        self.assertFalse((cache / "oracles" / reference["tag"]).exists())

    def test_active_release_uses_01660_asset_checksums(self):
        _, _, oracle_sha, manifest_sha = metadata_for(reference_for("active"))
        self.assertEqual(oracle_sha, "349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735")
        self.assertEqual(manifest_sha, "344d6fc1c6d25f1ea49d96a8c938a765c5af1787629858dc83abf7d87ce75b0b")

    def test_04391_regression_uses_recorded_historical_asset_checksums(self):
        _, _, oracle_sha, manifest_sha = metadata_for(reference_for("0.439.1"))
        self.assertEqual(oracle_sha, "b4511d679dd6da53f706400dba5b368ffc5b5663f8764fa0c8f148b358b9255a")
        self.assertEqual(manifest_sha, "f5f4269d90de95c1cde06043df21c00a253681fcc96a8589cae067beb2fb95d9")

    def test_historical_oracle_accepts_its_version_specific_override(self):
        reference = reference_for("0.165.1")
        configured = Path(self.temporary.name) / "historical-oracle"
        configured.write_bytes(b"historical oracle")
        expected = hashlib.sha256(configured.read_bytes()).hexdigest()
        with patch.dict(os.environ, {"PRODEX_ORACLE_01651": str(configured)}):
            with patch("scripts.ci.reference.metadata_for", return_value=(Path("evidence"), "prodex", expected, "0" * 64)):
                self.assertEqual(acquire_oracle(reference), configured.resolve())

    def test_source_acquisition_requires_recorded_tag_and_matching_evidence_commit(self):
        reference = reference_for("active").copy()
        reference["tag_resolution_matches"] = False
        with self.assertRaisesRegex(SystemExit, "does not record a verified tag resolution"):
            metadata_for(reference)
        reference = reference_for("active").copy()
        reference["commit"] = "f" * 40
        with self.assertRaisesRegex(SystemExit, "source commit does not match"):
            metadata_for(reference)
        reference = reference_for("active").copy()
        reference["tag"] = "0.439.1"
        with self.assertRaisesRegex(SystemExit, "release version does not match"):
            metadata_for(reference)

    def test_source_recovery_fetches_the_pinned_commit_after_an_absent_tag(self):
        reference = {"repository": str(self.checkout), "tag": "synthetic", "commit": self.commit}
        cache = Path(self.temporary.name) / "cache"
        with patch.dict(os.environ, {"MODEX_REFERENCE_CACHE": str(cache)}):
            with patch("scripts.ci.reference.reference_for", return_value=reference):
                with patch("scripts.ci.reference.metadata_for", return_value=(Path("evidence"), "prodex", "0" * 64, "0" * 64)):
                    with patch("scripts.ci.reference.verify_tag", return_value=False):
                        source = acquire_source("active")
        self.assertEqual(source, (cache / "references" / f"prodex-{self.commit}").resolve())
        self.assertEqual(
            subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip(),
            self.commit,
        )

    def test_invalid_pinned_evidence_stops_before_tag_lookup_or_source_fetch(self):
        with patch.dict(os.environ, {"MODEX_REFERENCE_CACHE": str(Path(self.temporary.name) / "cache")}):
            with patch("scripts.ci.reference.reference_for", return_value=reference_for("active")):
                with patch("scripts.ci.reference.metadata_for", side_effect=SystemExit("invalid pinned evidence")):
                    with patch("scripts.ci.reference.verify_tag") as verify_tag:
                        with patch("scripts.ci.reference.subprocess.run") as run:
                            with self.assertRaisesRegex(SystemExit, "invalid pinned evidence"):
                                acquire_source("active")
        verify_tag.assert_not_called()
        run.assert_not_called()

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
        active_reference = {"tag": "0.166.0", "oracle": "prodex"}
        with patch.dict(os.environ, {"MODEX_REFERENCE_CACHE": str(cache), "PRODEX_ORACLE": str(configured)}):
            with patch("scripts.ci.reference.metadata_for", return_value=(Path("evidence"), "prodex", historical_sha, "0" * 64)):
                self.assertEqual(acquire_oracle(historical_reference), historical.resolve())
            with patch("scripts.ci.reference.metadata_for", return_value=(Path("evidence"), "prodex", active_sha, "0" * 64)):
                self.assertEqual(acquire_oracle(active_reference, active=True), configured.resolve())


class FrozenTagVerificationTests(unittest.TestCase):
    def assert_rejected_remote_listing(self, stdout):
        reference = reference_for("0.439.2")
        result = subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")
        with patch("scripts.ci.reference.subprocess.run", return_value=result):
            with self.assertRaises(SystemExit) as error:
                verify_tag(reference)
        self.assertNotIn("is missing;", str(error.exception), "malformed output must not be classified as an absent tag")

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

    def test_exact_lightweight_and_annotated_tags_are_accepted(self):
        reference = reference_for("0.439.2")
        expected = reference["commit"]
        listings = (
            f"{expected}\trefs/tags/0.439.2\n",
            f"{'a' * 40}\trefs/tags/0.439.2\n{expected}\trefs/tags/0.439.2^{{}}\n",
        )
        for listing in listings:
            result = subprocess.CompletedProcess(args=[], returncode=0, stdout=listing, stderr="")
            with patch("scripts.ci.reference.subprocess.run", return_value=result):
                self.assertTrue(verify_tag(reference))

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

    def test_repository_local_url_rewrite_cannot_execute_ssh_command(self):
        with tempfile.TemporaryDirectory(prefix="modex-reference-git-config-") as temporary:
            root = Path(temporary)
            checkout = root / "source"
            checkout.mkdir()
            subprocess.run(["git", "init", "--quiet", "--template=", str(checkout)], check=True)
            marker = root / "ssh-command-ran"
            command = root / "ssh-command"
            command.write_text(f"#!/bin/sh\nprintf ran > {marker}\nexit 0\n", encoding="utf-8")
            command.chmod(0o755)
            subprocess.run(["git", "-C", str(checkout), "config", "core.sshCommand", str(command)], check=True)
            subprocess.run([
                "git", "-C", str(checkout), "config",
                "url.ssh://127.0.0.1/fake.insteadOf",
                "https://github.com/christiandoxa/prodex",
            ], check=True)

            original_cwd = Path.cwd()
            try:
                os.chdir(checkout)
                proxy = "http://127.0.0.1:1"
                with patch.dict(os.environ, {
                    "HTTPS_PROXY": proxy, "https_proxy": proxy,
                    "HTTP_PROXY": proxy, "http_proxy": proxy,
                    "ALL_PROXY": proxy, "all_proxy": proxy,
                    "NO_PROXY": "", "no_proxy": "",
                }):
                    with self.assertRaisesRegex(SystemExit, "could not verify official Prodex tag"):
                        verify_tag(reference_for("active"), allow_missing=True)
            finally:
                os.chdir(original_cwd)
            self.assertFalse(marker.exists(), "repository-local core.sshCommand ran during tag verification")

    def test_duplicate_exact_tag_refs_are_rejected_even_when_one_matches(self):
        expected = reference_for("0.439.2")["commit"]
        self.assert_rejected_remote_listing(
            f"{'b' * 40}\trefs/tags/0.439.2\n{expected}\trefs/tags/0.439.2\n"
        )

    def test_orphan_peeled_tag_ref_is_not_a_valid_resolution(self):
        expected = reference_for("0.439.2")["commit"]
        self.assert_rejected_remote_listing(f"{expected}\trefs/tags/0.439.2^{{}}\n")

    def test_unexpected_remote_output_is_not_treated_as_a_valid_or_missing_tag(self):
        expected = reference_for("0.439.2")["commit"]
        self.assert_rejected_remote_listing(f"warning: unexpected response\n{expected}\trefs/tags/0.439.2\n")

    def test_missing_tag_is_allowed_only_when_source_acquisition_requests_it(self):
        reference = reference_for("0.439.2")
        missing = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with patch("scripts.ci.reference.subprocess.run", return_value=missing):
            self.assertFalse(verify_tag(reference, allow_missing=True))

    def test_remote_diagnostics_are_not_classified_as_an_absent_tag(self):
        reference = reference_for("0.439.2")
        warning = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="warning: remote lookup incomplete")
        with patch("scripts.ci.reference.subprocess.run", return_value=warning):
            with self.assertRaisesRegex(SystemExit, "could not verify official Prodex tag.*remote lookup incomplete"):
                verify_tag(reference, allow_missing=True)

    def test_missing_previous_release_tag_is_reported_without_fallback(self):
        reference = reference_for("0.439.1")
        missing = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with patch("scripts.ci.reference.subprocess.run", return_value=missing):
            with self.assertRaisesRegex(SystemExit, r"official Prodex tag 0\.439\.1 is missing"):
                verify_tag(reference)


if __name__ == "__main__":
    unittest.main()
