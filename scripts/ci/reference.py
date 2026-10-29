#!/usr/bin/env python3
"""Acquire only checksum-verified official baseline assets for CI."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[2]
BASELINE = json.loads((ROOT / "docs/baseline.json").read_text(encoding="utf-8"))
NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def reference_for(version: str) -> dict:
    active = BASELINE["reference"]
    if version in ("active", active["tag"]):
        return active
    if version == "previous":
        reference = BASELINE.get("previous_reference")
        if not reference:
            raise SystemExit("baseline does not declare a previous reference")
        return reference
    references = [BASELINE.get("previous_reference", {})]
    references.extend(BASELINE.get("historical_references", []))
    for item in references:
        if item.get("tag") == version:
            return item
    raise SystemExit(f"baseline does not declare reference {version!r}")


def verified_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def metadata_for(reference: dict) -> tuple[Path, str, str, str]:
    if reference.get("repository") != "https://github.com/christiandoxa/prodex":
        raise SystemExit("CI reference acquisition is restricted to the frozen Prodex repository")
    if reference.get("tag_resolution_matches") is not True:
        raise SystemExit(f"reference {reference.get('tag')!r} does not record a verified tag resolution")
    commit = reference.get("commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise SystemExit(f"reference {reference.get('tag')!r} does not record a pinned source commit")
    evidence_path = Path(reference["evidence"])
    if evidence_path.is_absolute() or ".." in evidence_path.parts:
        raise SystemExit("baseline evidence paths must be repository-relative")
    evidence_path = ROOT / evidence_path
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if evidence.get("commit", evidence.get("baseline_commit")) != commit:
        raise SystemExit(f"{evidence_path}: frozen source commit does not match the baseline reference")
    if evidence.get("version") != reference.get("tag"):
        raise SystemExit(f"{evidence_path}: release version does not match the baseline reference")
    name = Path(reference["oracle"]).name
    assets = evidence.get("downloaded_asset_sha256", {})
    oracle_sha = evidence.get("linux_oracle_sha256") or assets.get(name)
    manifest_sha = evidence.get("sha256sums_sha256") or assets.get("SHA256SUMS")
    if not isinstance(oracle_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", oracle_sha):
        raise SystemExit(f"{evidence_path}: missing pinned Linux oracle SHA-256")
    if not isinstance(manifest_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", manifest_sha):
        raise SystemExit(f"{evidence_path}: missing pinned official SHA256SUMS SHA-256")
    tag = reference["tag"]
    if not NAME.fullmatch(name) or not NAME.fullmatch(tag):
        raise SystemExit("baseline tag or oracle asset name contains unsupported characters")
    return evidence_path, name, oracle_sha, manifest_sha


def download(url: str, destination: Path) -> None:
    with urlopen(url, timeout=60) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)


def git_environment() -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update({
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
    })
    return environment


def run_git(*args: str, timeout: int = 30, **kwargs):
    return subprocess.run(
        ["git", "--no-replace-objects", "-c", "core.fsmonitor=false", *args],
        env=git_environment(), timeout=timeout, **kwargs,
    )


def acquire_oracle(reference: dict, *, active: bool = False) -> Path:
    _, name, oracle_sha, manifest_sha = metadata_for(reference)
    configured = os.environ.get("PRODEX_ORACLE") if active else None
    if not configured:
        configured = os.environ.get(f"PRODEX_ORACLE_{reference['tag'].replace('.', '')}")
    cache = Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
    target = Path(configured).expanduser() if configured else cache / "oracles" / reference["tag"] / name
    if target.is_file():
        actual = verified_digest(target)
        if actual != oracle_sha:
            raise SystemExit(f"pinned oracle checksum mismatch at {target}: {actual}")
        return target.resolve()
    if configured:
        raise SystemExit(f"PRODEX_ORACLE does not exist: {target}")

    verify_tag(reference)
    release = f"{reference['repository']}/releases/download/{reference['tag']}"
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="modex-oracle-") as temporary:
        work = Path(temporary)
        manifest = work / "SHA256SUMS"
        asset = work / name
        download(f"{release}/SHA256SUMS", manifest)
        actual_manifest_sha = verified_digest(manifest)
        if actual_manifest_sha != manifest_sha:
            raise SystemExit(
                f"official SHA256SUMS checksum mismatch: expected {manifest_sha}, got {actual_manifest_sha}"
            )
        matches = [line.split() for line in manifest.read_text(encoding="utf-8").splitlines()
                   if line.split() and line.split()[-1].lstrip("*") == name]
        if len(matches) != 1 or matches[0][0] != oracle_sha:
            raise SystemExit("the official SHA256SUMS entry does not match the pinned oracle checksum")
        download(f"{release}/{name}", asset)
        actual_oracle_sha = verified_digest(asset)
        if actual_oracle_sha != oracle_sha:
            raise SystemExit(f"official oracle checksum mismatch: expected {oracle_sha}, got {actual_oracle_sha}")
        asset.chmod(0o755)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(asset, target)
    print(f"verified {reference['tag']} oracle {oracle_sha}", file=sys.stderr)
    return target.resolve()


def verify_tag(reference: dict, *, allow_missing: bool = False) -> bool:
    repository = reference["repository"]
    if repository != "https://github.com/christiandoxa/prodex":
        raise SystemExit("CI source acquisition is restricted to the frozen Prodex repository")
    tag = reference["tag"]
    expected = reference["commit"]
    if not re.fullmatch(r"[0-9a-f]{40}", expected):
        raise SystemExit(f"invalid frozen commit for reference {tag}")
    try:
        # Keep caller-repository URL rewrites and SSH commands out of this lookup.
        result = run_git(
            "ls-remote", repository, f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}",
            check=True, text=True, capture_output=True, timeout=30, cwd="/",
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        detail = getattr(error, "stderr", "")
        raise SystemExit(f"could not verify official Prodex tag {tag}: {detail or error}") from error
    if result.stderr:
        raise SystemExit(f"could not verify official Prodex tag {tag}: {result.stderr.strip()}")
    names = (f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}")
    if not result.stdout:
        if allow_missing:
            return False
        raise SystemExit(
            f"official Prodex tag {tag} is missing; expected frozen commit {expected}. "
            "The baseline reference is unavailable; refusing to substitute another version."
        )
    resolved = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        if (len(fields) != 2 or not re.fullmatch(r"[0-9a-f]{40}", fields[0])
                or fields[1] not in names or fields[1] in resolved):
            raise SystemExit(f"official Prodex tag {tag} lookup returned malformed or ambiguous output")
        resolved[fields[1]] = fields[0]
    if not resolved or (names[1] in resolved and names[0] not in resolved):
        raise SystemExit(f"official Prodex tag {tag} lookup returned malformed or ambiguous output")
    actual = resolved.get(f"refs/tags/{tag}^{{}}", resolved.get(f"refs/tags/{tag}"))
    if actual != expected:
        raise SystemExit(f"official tag {tag} resolves to {actual!r}, expected frozen commit {expected}")
    return True


def verify_cached_source(target: Path, expected_commit: str) -> None:
    """Reject cached worktrees whose contents differ from the frozen Git tree."""
    def git(*args: str, timeout: int = 30) -> bytes:
        try:
            return run_git(
                "-C", str(target), *args, check=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
            ).stdout
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            detail = getattr(error, "stderr", b"")
            raise SystemExit(f"cached source snapshot is not a verifiable Git checkout: {target}: "
                             f"{detail.decode(errors='replace') if isinstance(detail, bytes) else detail or error}") from error

    try:
        info = os.lstat(target)
    except OSError as error:
        raise SystemExit(f"cached source snapshot is not a verifiable Git checkout: {target}: {error}") from error
    if not stat.S_ISDIR(info.st_mode):
        raise SystemExit(f"cached source snapshot is not a verifiable Git checkout: {target}")
    try:
        git_info = os.lstat(target / ".git")
    except OSError as error:
        raise SystemExit(f"cached source snapshot has no isolated Git metadata: {target}") from error
    if not stat.S_ISDIR(git_info.st_mode):
        raise SystemExit(f"cached source snapshot has no isolated Git metadata: {target}")

    root = Path(os.fsdecode(git("rev-parse", "--show-toplevel")).strip()).resolve()
    head = os.fsdecode(git("rev-parse", "--verify", "HEAD^{commit}")).strip()
    object_format = git("rev-parse", "--show-object-format").strip()
    if root != target.resolve() or head != expected_commit or object_format != b"sha1":
        raise SystemExit(f"cached source snapshot has the wrong checkout or commit: {target}")

    object_format = os.fsdecode(object_format).strip()
    tree_entries = git("ls-tree", "-r", "-z", expected_commit, timeout=60)
    expected_files = {}
    directories = set()
    for entry in tree_entries.split(b"\0"):
        if not entry:
            continue
        metadata, relative = entry.split(b"\t", 1)
        mode, kind, expected_blob = metadata.split()
        if kind != b"blob" or mode not in (b"100644", b"100755", b"120000"):
            raise SystemExit(f"cached source snapshot contains an unsupported Git entry: {target}")
        if relative in expected_files:
            raise SystemExit(f"cached source snapshot has ambiguous Git tree entries: {target}")
        expected_files[relative] = (mode, expected_blob)
        components = relative.split(b"/")
        directories.update(b"/".join(components[:index]) for index in range(1, len(components)))

    seen_files = set()
    root_bytes = os.fsencode(target.resolve())
    try:
        for current, child_dirs, child_files in os.walk(root_bytes, followlinks=False):
            relative_dir = os.path.relpath(current, root_bytes)
            if relative_dir == b".":
                if b".git" not in child_dirs:
                    raise SystemExit(f"cached source snapshot has no isolated Git metadata: {target}")
                child_dirs.remove(b".git")
            relative_dir = b"" if relative_dir == b"." else relative_dir
            for name in child_dirs[:]:
                relative = os.path.join(relative_dir, name) if relative_dir else name
                path_bytes = os.path.join(current, name)
                info = os.lstat(path_bytes)
                if stat.S_ISLNK(info.st_mode):
                    child_dirs.remove(name)
                    child_files.append(name)
                elif relative not in directories:
                    raise SystemExit(f"cached source snapshot is dirty or contains untracked files: {target}")
            for name in child_files:
                relative = os.path.join(relative_dir, name) if relative_dir else name
                expected = expected_files.get(relative)
                if expected is None:
                    raise SystemExit(f"cached source snapshot is dirty or contains untracked files: {target}")
                mode, expected_blob = expected
                path_bytes = os.path.join(current, name)
                info = os.lstat(path_bytes)
                if mode == b"120000":
                    if not stat.S_ISLNK(info.st_mode):
                        raise SystemExit(f"cached source snapshot changed a tracked symlink: {target}")
                    contents = os.fsencode(os.readlink(path_bytes))
                else:
                    if not stat.S_ISREG(info.st_mode):
                        raise SystemExit(f"cached source snapshot changed a tracked file type: {target}")
                    executable = bool(info.st_mode & 0o111)
                    if executable != (mode == b"100755"):
                        raise SystemExit(f"cached source snapshot changed a tracked file mode: {target}")
                    with open(path_bytes, "rb") as source:
                        contents = source.read()
                digest = hashlib.new(object_format)
                digest.update(f"blob {len(contents)}\0".encode("ascii"))
                digest.update(contents)
                if digest.hexdigest().encode("ascii") != expected_blob:
                    raise SystemExit(f"cached source snapshot has modified tracked content: {target}")
                seen_files.add(relative)
    except OSError as error:
        raise SystemExit(f"cached source snapshot could not be read safely: {target}: {error}") from error
    if seen_files != expected_files.keys():
        raise SystemExit(f"cached source snapshot is missing a tracked file: {target}")


def acquire_source(version: str) -> Path:
    reference = reference_for(version)
    metadata_for(reference)
    tag_present = verify_tag(reference, allow_missing=True)
    if not tag_present:
        print(
            f"official Prodex tag {reference['tag']} is missing; recovering source at pinned commit "
            f"{reference['commit']}",
            file=sys.stderr,
        )
    cache = Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
    target = cache / "references" / f"prodex-{reference['commit']}"
    if target.exists():
        verify_cached_source(target, reference["commit"])
        return target.resolve()

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="modex-source-", dir=target.parent) as temporary:
        checkout = Path(temporary) / "source"
        checkout.mkdir()
        run_git("init", "--quiet", "--template=", str(checkout), check=True, timeout=10)
        run_git("-C", str(checkout), "remote", "add", "origin", reference["repository"], check=True, timeout=10)
        run_git("-C", str(checkout), "fetch", "--quiet", "--depth=1", "origin", reference["commit"],
                check=True, timeout=120)
        run_git("-C", str(checkout), "checkout", "--quiet", "--detach", "FETCH_HEAD", check=True, timeout=30)
        actual = run_git("-C", str(checkout), "rev-parse", "--verify", "HEAD^{commit}", check=True,
                         text=True, capture_output=True, timeout=10).stdout.strip()
        if actual != reference["commit"]:
            raise SystemExit(f"source checkout resolved to {actual}, expected {reference['commit']}")
        verify_cached_source(checkout, reference["commit"])
        os.replace(checkout, target)
    print(f"verified {version} source commit {reference['commit']}", file=sys.stderr)
    return target.resolve()


def reference_identity(reference: dict) -> dict:
    evidence_path, name, oracle_sha, manifest_sha = metadata_for(reference)
    return {
        "repository": reference["repository"],
        "tag": reference["tag"],
        "commit": reference["commit"],
        "oracle_asset": name,
        "oracle_sha256": oracle_sha,
        "sha256sums_sha256": manifest_sha,
        "evidence": evidence_path.relative_to(ROOT).as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("oracle", "source", "identity"))
    parser.add_argument("version", nargs="?", default="active")
    args = parser.parse_args()
    reference = reference_for(args.version)
    if args.kind == "oracle":
        active = reference["commit"] == BASELINE["reference"]["commit"]
        print(acquire_oracle(reference, active=active))
    elif args.kind == "source":
        print(acquire_source(args.version))
    else:
        print(json.dumps(reference_identity(reference), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
