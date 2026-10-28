#!/usr/bin/env python3
"""Create and verify immutable manifests for same-run CI build artifacts."""

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import secrets
import subprocess
import tarfile


FORMAT = "modex-ci-artifact-manifest"
VERSION = 1
MANIFEST_MODE = 0o444
CHUNK_SIZE = 1024 * 1024
MAX_BUNDLE_MEMBER_SIZE = 1024 * 1024 * 1024
MAX_BUNDLE_SIZE = MAX_BUNDLE_MEMBER_SIZE + 8 * 1024 * 1024
MAX_MANIFEST_SIZE = 4 * 1024 * 1024
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class ManifestError(ValueError):
    """Raised when artifact provenance or bytes do not match expectations."""


def _require(condition, message):
    if not condition:
        raise ManifestError(message)


def _canonical_json(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def _safe_relative_path(value):
    _require(isinstance(value, str) and value, "artifact path must be a non-empty string")
    _require("\\" not in value and "\x00" not in value, f"invalid artifact path: {value!r}")
    parts = value.split("/")
    _require(
        not value.startswith("/")
        and ":" not in parts[0]
        and all(part not in ("", ".", "..") for part in parts),
        f"artifact path must be normalized and relative: {value!r}",
    )
    _require(all(not any(ord(character) < 32 for character in part) for part in parts),
             f"artifact path contains a control character: {value!r}")
    return PurePosixPath(value)


def _open_root(path):
    raw = os.fspath(path)
    if not os.path.isabs(raw):
        _require(".." not in raw.split(os.sep), "relative artifact root must not contain parent traversal")
        raw = os.path.join(os.getcwd(), raw)
    fd, _ = _open_absolute(raw, os.O_RDONLY | os.O_DIRECTORY, "artifact root")
    return fd


def _absolute_parts(path, label):
    raw = os.fspath(path)
    _require(isinstance(raw, str) and raw.startswith(os.sep) and not raw.startswith(os.sep * 2),
             f"{label} path must be absolute: {raw!r}")
    _require("\x00" not in raw and ".." not in raw.split(os.sep),
             f"{label} path contains an invalid component: {raw!r}")
    parts = [part for part in raw.split(os.sep) if part not in ("", ".")]
    _require(parts, f"{label} path cannot be the filesystem root")
    return parts, os.sep + os.sep.join(parts)


def _open_absolute(path, final_flags, label):
    _require(getattr(os, "O_DIRECTORY", 0) and getattr(os, "O_NOFOLLOW", 0),
             "platform lacks safe directory-open flags")
    parts, absolute = _absolute_parts(path, label)
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    try:
        current_fd = os.open(os.sep, directory_flags)
    except OSError as error:
        raise ManifestError(f"cannot safely open filesystem root for {label}: {error}") from error
    try:
        for component in parts[:-1]:
            next_fd = os.open(component, directory_flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        fd = os.open(parts[-1], final_flags | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
                     dir_fd=current_fd)
        return fd, absolute
    except OSError as error:
        raise ManifestError(f"cannot safely traverse {label} path {absolute}: {error}") from error
    finally:
        os.close(current_fd)


def _open_directory_path(path, label):
    fd, absolute = _open_absolute(path, os.O_RDONLY | os.O_DIRECTORY, label)
    info = os.fstat(fd)
    if not stat.S_ISDIR(info.st_mode):
        os.close(fd)
        raise ManifestError(f"{label} must be a real directory: {absolute}")
    return fd


def _open_parent(root_fd, relative):
    path = _safe_relative_path(relative)
    current_fd = os.dup(root_fd)
    try:
        for component in path.parts[:-1]:
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
            next_fd = os.open(component, flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd, path.name
    except OSError as error:
        os.close(current_fd)
        raise ManifestError(f"cannot safely traverse artifact path {relative!r}: {error}") from error


def _read_fd(fd, label, require_single_link=False, max_size=None):
    before = os.fstat(fd)
    _require(stat.S_ISREG(before.st_mode), f"artifact is not a regular file: {label}")
    if require_single_link:
        _require(before.st_nlink == 1, f"artifact has multiple hard links: {label}")
    if max_size is not None:
        _require(before.st_size <= max_size, f"manifest is too large: {label}")
    digest = hashlib.sha256()
    content = bytearray() if max_size is not None else None
    total = 0
    while True:
        chunk = os.read(fd, CHUNK_SIZE)
        if not chunk:
            break
        digest.update(chunk)
        total += len(chunk)
        if content is not None:
            content.extend(chunk)
            _require(total <= max_size, f"manifest is too large: {label}")
    after = os.fstat(fd)
    before_state = (before.st_dev, before.st_ino, before.st_size, before.st_mode,
                    before.st_mtime_ns, before.st_ctime_ns)
    after_state = (after.st_dev, after.st_ino, after.st_size, after.st_mode,
                   after.st_mtime_ns, after.st_ctime_ns)
    _require(before_state == after_state and total == before.st_size,
             f"file changed while it was being read: {label}")
    return {
        "mode": stat.S_IMODE(before.st_mode),
        "size": total,
        "sha256": digest.hexdigest(),
    }, bytes(content) if content is not None else None


def _hash_relative_file(root_fd, relative):
    parent_fd, leaf = _open_parent(root_fd, relative)
    try:
        flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        fd = os.open(leaf, flags, dir_fd=parent_fd)
        try:
            info, _ = _read_fd(fd, relative, require_single_link=True)
            return {"path": str(_safe_relative_path(relative)), **info}
        finally:
            os.close(fd)
    except OSError as error:
        raise ManifestError(f"cannot safely read artifact {relative!r}: {error}") from error
    finally:
        os.close(parent_fd)


def _hash_absolute_file(path, label, require_executable=False):
    fd, absolute = _open_absolute(path, os.O_RDONLY, label)
    try:
        metadata, _ = _read_fd(fd, absolute)
    finally:
        os.close(fd)
    if require_executable:
        _require(metadata["mode"] & 0o111, f"compiler is not executable: {absolute}")
    return {"name": absolute.rsplit(os.sep, 1)[-1], **metadata}


def _compiler_identity(path, expected_version):
    before = _hash_absolute_file(path, "compiler", require_executable=True)
    _require(before["mode"] & 0o022 == 0, "compiler must not be group- or world-writable")
    _, absolute = _absolute_parts(path, "compiler")
    try:
        result = subprocess.run(
            [absolute, "--version"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
            timeout=15, check=False, cwd=os.sep,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ManifestError(f"cannot query Mojo compiler version: {error}") from error
    _require(result.returncode == 0,
             f"Mojo compiler --version failed with exit code {result.returncode}")
    actual_version = result.stdout.strip()
    _require(actual_version and "\n" not in actual_version and "\r" not in actual_version,
             "Mojo compiler returned an invalid version string")
    _require(actual_version == expected_version,
             f"Mojo compiler version mismatch: expected {expected_version!r}, found {actual_version!r}")
    after = _hash_absolute_file(path, "compiler", require_executable=True)
    _require(before == after, "Mojo compiler changed while its version was queried")
    return {**after, "version": actual_version}


def _runtime_identity(path, expected_version):
    before = _hash_absolute_file(path, "runtime", require_executable=True)
    _require(before["mode"] & 0o022 == 0, "runtime must not be group- or world-writable")
    _, absolute = _absolute_parts(path, "runtime")
    try:
        result = subprocess.run(
            [absolute, "--version"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
            timeout=15, check=False, cwd=os.sep,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ManifestError(f"cannot query compiler runtime version: {error}") from error
    _require(result.returncode == 0, "compiler runtime --version failed")
    actual_version = result.stdout.strip() or result.stderr.strip()
    _require(actual_version and "\n" not in actual_version and "\r" not in actual_version,
             "compiler runtime returned an invalid version string")
    _require(actual_version == expected_version,
             f"compiler runtime version mismatch: expected {expected_version!r}, found {actual_version!r}")
    after = _hash_absolute_file(path, "runtime", require_executable=True)
    _require(before == after, "compiler runtime changed while its version was queried")
    return {**after, "version": actual_version}


def _walk_tree(dir_fd, prefix=""):
    records = []
    try:
        names = sorted(os.listdir(dir_fd))
    except OSError as error:
        raise ManifestError(f"cannot list standard-library directory: {error}") from error
    for name in names:
        _require(name not in (".", "..") and "/" not in name and "\\" not in name,
                 f"invalid standard-library entry name: {name!r}")
        try:
            info = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
        except OSError as error:
            raise ManifestError(f"cannot inspect standard-library entry {name!r}: {error}") from error
        if stat.S_ISDIR(info.st_mode):
            if name == "__pycache__":
                continue
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
            try:
                child_fd = os.open(name, flags, dir_fd=dir_fd)
                try:
                    children = _walk_tree(child_fd, f"{prefix}{name}/")
                finally:
                    os.close(child_fd)
            except OSError as error:
                raise ManifestError(f"cannot safely traverse standard-library entry {name!r}: {error}") from error
            records.extend(children)
        elif stat.S_ISREG(info.st_mode):
            relative = f"{prefix}{name}"
            try:
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
                             dir_fd=dir_fd)
                try:
                    metadata, _ = _read_fd(fd, relative, require_single_link=True)
                finally:
                    os.close(fd)
            except OSError as error:
                raise ManifestError(f"cannot safely read standard-library file {relative!r}: {error}") from error
            records.append({"path": relative, **metadata})
        else:
            raise ManifestError(f"standard-library tree contains a symlink or special file: {prefix}{name}")
    return records


def _stdlib_identity(version, roots):
    _require(isinstance(version, str) and version.strip(), "stdlib version must be non-empty")
    _require(set(roots) == {"modular", "mojo"},
             "stdlib identity requires exactly the modular and mojo package roots")
    root_records = []
    for name in sorted(roots):
        root_fd = _open_directory_path(roots[name], f"stdlib {name}")
        try:
            files = _walk_tree(root_fd)
        finally:
            os.close(root_fd)
        _require(files, f"stdlib package root is empty: {name}")
        root_records.append({
            "name": name,
            "files": files,
            "sha256": hashlib.sha256(_canonical_json(files)).hexdigest(),
        })
    payload = {"version": version, "roots": root_records}
    return {**payload, "sha256": hashlib.sha256(_canonical_json(payload)).hexdigest()}


def _identity(source_commit, run_id, run_attempt, producer_job, target, target_cpu,
              build_flags, expected_compiler_version, compiler_path,
              expected_runtime_version, runtime_path,
              stdlib_version, stdlib_roots):
    _require(isinstance(source_commit, str) and COMMIT_RE.fullmatch(source_commit),
             "source commit must be a lowercase 40- or 64-character Git object ID")
    _require(isinstance(run_id, str) and re.fullmatch(r"[0-9]+", run_id),
             "run ID must be a positive decimal string")
    _require(int(run_id) > 0, "run ID must be positive")
    _require(isinstance(run_attempt, int) and not isinstance(run_attempt, bool) and run_attempt > 0,
             "run attempt must be a positive integer")
    _require(isinstance(producer_job, str) and NAME_RE.fullmatch(producer_job),
             "producer job must be a simple job identifier")
    _require(isinstance(target, str) and NAME_RE.fullmatch(target),
             "target must be a simple target identifier")
    _require(isinstance(target_cpu, str) and NAME_RE.fullmatch(target_cpu),
             "target CPU must be a simple CPU identifier")
    _require(isinstance(build_flags, (list, tuple)) and build_flags
             and all(isinstance(flag, str) and flag and "\x00" not in flag for flag in build_flags),
             "build flags must be a non-empty ordered list of argument strings")
    cpu_values = []
    index = 0
    while index < len(build_flags):
        flag = build_flags[index]
        if flag == "--target-cpu":
            _require(index + 1 < len(build_flags), "--target-cpu flag is missing its value")
            cpu_values.append(build_flags[index + 1])
            index += 1
        elif flag.startswith("--target-cpu="):
            cpu_values.append(flag.partition("=")[2])
        index += 1
    _require(cpu_values == [target_cpu],
             "build flags must contain exactly one --target-cpu matching target CPU")
    _require(isinstance(expected_compiler_version, str) and expected_compiler_version.strip(),
             "expected compiler version must be non-empty")
    compiler = _compiler_identity(compiler_path, expected_compiler_version)
    runtime = _runtime_identity(runtime_path, expected_runtime_version)
    return {
        "source_commit": source_commit,
        "producer": {"run_id": run_id, "run_attempt": run_attempt, "job": producer_job},
        "target": target,
        "build": {"flags": list(build_flags), "target_cpu": target_cpu},
        "compiler": compiler,
        "runtime": runtime,
        "stdlib": _stdlib_identity(stdlib_version, stdlib_roots),
    }


def extract_bundle(bundle_path, destination, expected_bundle_sha256):
    """Extract only the regular files used by the fast CI build handoff."""
    _require(isinstance(expected_bundle_sha256, str)
             and HASH_RE.fullmatch(expected_bundle_sha256),
             "expected artifact bundle digest must be a lowercase SHA-256")
    root_fd = _open_root(destination)
    try:
        _require(not os.listdir(root_fd), "artifact extraction directory must be empty")
        fd, absolute = _open_absolute(bundle_path, os.O_RDONLY, "artifact bundle")
        try:
            before = os.fstat(fd)
            _require(stat.S_ISREG(before.st_mode), "artifact bundle is not a regular file")
            _require(before.st_nlink == 1, "artifact bundle has multiple hard links")
            _require(before.st_size <= MAX_BUNDLE_SIZE, "artifact bundle is too large")
            metadata, _ = _read_fd(fd, absolute, require_single_link=True)
            _require(hmac.compare_digest(metadata["sha256"], expected_bundle_sha256),
                     "artifact bundle digest does not match the trusted expected digest")
            os.lseek(fd, 0, os.SEEK_SET)
            bundle = os.fdopen(os.dup(fd), "rb")
            try:
                with tarfile.open(fileobj=bundle, mode="r:") as archive:
                    members = archive.getmembers()
                    expected = {"manifest.json": (MANIFEST_MODE, MAX_MANIFEST_SIZE),
                                "modex": (0o755, MAX_BUNDLE_MEMBER_SIZE)}
                    _require(
                        len(members) == len(expected)
                        and [member.name for member in members] == sorted(expected),
                        "artifact bundle must contain exactly manifest.json and modex",
                    )
                    for member in members:
                        expected_mode, max_size = expected[member.name]
                        _require(member.type in (tarfile.REGTYPE, tarfile.AREGTYPE)
                                 and member.mode == expected_mode,
                                 f"invalid artifact bundle entry: {member.name!r}")
                        # shortcut: bundles with files above 1 GiB are rejected; raise after measuring compiler growth.
                        _require(0 <= member.size <= max_size,
                                 f"artifact bundle member is too large: {member.name}")
                    for member in members:
                        source = archive.extractfile(member)
                        _require(source is not None, f"cannot read artifact bundle member: {member.name}")
                        out_fd = os.open(
                            member.name,
                            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                            | getattr(os, "O_CLOEXEC", 0),
                            0o600,
                            dir_fd=root_fd,
                        )
                        try:
                            total = 0
                            with source:
                                while True:
                                    chunk = source.read(CHUNK_SIZE)
                                    if not chunk:
                                        break
                                    total += len(chunk)
                                    _require(total <= member.size,
                                             f"artifact bundle member grew while reading: {member.name}")
                                    view = memoryview(chunk)
                                    while view:
                                        written = os.write(out_fd, view)
                                        _require(written > 0, "short write while extracting artifact bundle")
                                        view = view[written:]
                            _require(total == member.size,
                                     f"artifact bundle member size mismatch: {member.name}")
                            os.fchmod(out_fd, member.mode)
                            os.fsync(out_fd)
                        finally:
                            os.close(out_fd)
                os.lseek(fd, 0, os.SEEK_SET)
                after, _ = _read_fd(fd, absolute, require_single_link=True)
                _require(hmac.compare_digest(after["sha256"], expected_bundle_sha256),
                         "artifact bundle changed while it was being extracted")
                return absolute
            except (tarfile.TarError, OSError) as error:
                raise ManifestError(f"cannot safely read artifact bundle {absolute}: {error}") from error
            finally:
                bundle.close()
        finally:
            os.close(fd)
    finally:
        os.close(root_fd)


def _manifest_structure(document):
    _require(isinstance(document, dict)
             and set(document) == {"format", "version", "identity", "files"},
             "manifest has invalid top-level fields")
    _require(document["format"] == FORMAT and document["version"] == VERSION,
             "unsupported artifact manifest format or version")
    _require(isinstance(document["identity"], dict), "manifest identity must be an object")
    _require(isinstance(document["files"], list) and document["files"],
             "manifest must list at least one artifact file")
    paths = []
    for entry in document["files"]:
        _require(isinstance(entry, dict) and set(entry) == {"path", "mode", "size", "sha256"},
                 "manifest file entry has invalid fields")
        path = str(_safe_relative_path(entry["path"]))
        _require(path == entry["path"], f"manifest path is not canonical: {entry['path']!r}")
        _require(isinstance(entry["mode"], int) and not isinstance(entry["mode"], bool)
                 and 0 <= entry["mode"] <= 0o7777, f"invalid file mode for {path}")
        _require(isinstance(entry["size"], int) and not isinstance(entry["size"], bool)
                 and entry["size"] >= 0, f"invalid file size for {path}")
        _require(isinstance(entry["sha256"], str) and HASH_RE.fullmatch(entry["sha256"]),
                 f"invalid SHA-256 for {path}")
        paths.append(path)
    _require(paths == sorted(set(paths)), "manifest file paths must be unique and sorted")
    return paths


def _manifest_path(relative, artifact_paths):
    manifest_path = str(_safe_relative_path(relative))
    _require(manifest_path not in artifact_paths, "manifest path must not also be an artifact file")
    return manifest_path


def _write_manifest(root_fd, relative, content):
    parent_fd, leaf = _open_parent(root_fd, relative)
    temp_name = f".{leaf}.tmp-{os.getpid()}-{secrets.token_hex(8)}"
    fd = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        fd = os.open(temp_name, flags, 0o600, dir_fd=parent_fd)
        view = memoryview(content)
        while view:
            written = os.write(fd, view)
            _require(written > 0, "short write while creating manifest")
            view = view[written:]
        os.fsync(fd)
        os.fchmod(fd, MANIFEST_MODE)
        os.fsync(fd)
        os.close(fd)
        fd = None
        os.link(temp_name, leaf, src_dir_fd=parent_fd, dst_dir_fd=parent_fd, follow_symlinks=False)
        os.unlink(temp_name, dir_fd=parent_fd)
        os.fsync(parent_fd)
    except OSError as error:
        raise ManifestError(f"cannot create immutable manifest {relative!r}: {error}") from error
    finally:
        if fd is not None:
            os.close(fd)
        try:
            os.unlink(temp_name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        os.close(parent_fd)


def create_manifest(root, manifest_path, identity, paths):
    _require(paths, "at least one artifact file is required")
    artifact_paths = [str(_safe_relative_path(path)) for path in paths]
    _require(artifact_paths == sorted(set(artifact_paths)),
             "artifact paths must be unique and sorted")
    manifest_path = _manifest_path(manifest_path, artifact_paths)
    root_fd = _open_root(root)
    try:
        files = [_hash_relative_file(root_fd, path) for path in artifact_paths]
        document = {"format": FORMAT, "version": VERSION, "identity": identity, "files": files}
        _manifest_structure(document)
        content = _canonical_json(document)
        _write_manifest(root_fd, manifest_path, content)
        return hashlib.sha256(content).hexdigest()
    finally:
        os.close(root_fd)


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, f"manifest contains duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value):
    raise ManifestError(f"manifest contains invalid JSON constant: {value}")


def _read_manifest(root_fd, relative):
    parent_fd, leaf = _open_parent(root_fd, relative)
    try:
        flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        try:
            fd = os.open(leaf, flags, dir_fd=parent_fd)
        except OSError as error:
            raise ManifestError(f"cannot safely open manifest {relative!r}: {error}") from error
        try:
            info, content = _read_fd(fd, relative, require_single_link=True, max_size=MAX_MANIFEST_SIZE)
        finally:
            os.close(fd)
    finally:
        os.close(parent_fd)
    _require(info["mode"] == MANIFEST_MODE,
             f"manifest permissions must be {MANIFEST_MODE:04o}, found {info['mode']:04o}")
    try:
        document = json.loads(content, object_pairs_hook=_no_duplicate_keys,
                              parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ManifestError(f"manifest is not valid UTF-8 JSON: {error}") from error
    _require(_canonical_json(document) == content, "manifest JSON is not canonical")
    _manifest_structure(document)
    return document, info["sha256"]


def verify_manifest(root, manifest_path, expected_manifest_sha256,
                    expected_identity, expected_paths):
    _require(isinstance(expected_manifest_sha256, str)
             and HASH_RE.fullmatch(expected_manifest_sha256),
             "expected manifest digest must be a lowercase SHA-256")
    artifact_paths = [str(_safe_relative_path(path)) for path in expected_paths]
    _require(artifact_paths and artifact_paths == sorted(set(artifact_paths)),
             "expected artifact paths must be non-empty, unique and sorted")
    manifest_path = _manifest_path(manifest_path, artifact_paths)
    root_fd = _open_root(root)
    try:
        document, manifest_digest = _read_manifest(root_fd, manifest_path)
        _require(hmac.compare_digest(manifest_digest, expected_manifest_sha256),
                 "manifest digest does not match the trusted expected digest")
        _require(document["identity"] == expected_identity,
                 "manifest source, producer, target, compiler, runtime or stdlib identity mismatch")
        actual_paths = _manifest_structure(document)
        _require(actual_paths == artifact_paths,
                 "manifest artifact paths do not match the expected file inventory")
        for expected, path in zip(document["files"], artifact_paths):
            actual = _hash_relative_file(root_fd, path)
            _require(actual == expected, f"artifact content, mode or size mismatch: {path}")
        return manifest_digest
    finally:
        os.close(root_fd)


def _parse_stdlib_roots(values):
    roots = {}
    for value in values:
        if "=" not in value:
            raise ManifestError("stdlib roots must use NAME=PATH")
        name, path = value.split("=", 1)
        if name not in ("modular", "mojo") or not path or name in roots:
            raise ManifestError("provide each of modular=PATH and mojo=PATH exactly once")
        roots[name] = path
    if set(roots) != {"modular", "mojo"}:
        raise ManifestError("provide both modular=PATH and mojo=PATH")
    return roots


def _add_identity_arguments(parser):
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True, type=int)
    parser.add_argument("--producer-job", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--target-cpu", required=True)
    parser.add_argument("--build-flag", action="append", required=True,
                         help="one Mojo build argv element; repeat in exact order")
    parser.add_argument("--compiler", required=True, help="path to the pinned Mojo compiler executable")
    parser.add_argument("--expected-compiler-version", required=True,
                         help="required exact output of the compiler's --version command")
    parser.add_argument("--runtime", required=True, help="path to the compiler's Python runtime executable")
    parser.add_argument("--expected-runtime-version", required=True,
                         help="required exact output of the runtime's --version command")
    parser.add_argument("--stdlib-version", required=True)
    parser.add_argument("--stdlib", action="append", required=True, metavar="NAME=PATH")


def _build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("create", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--root", required=True, help="artifact root containing the listed files")
        subparser.add_argument("--manifest", required=True, help="normalized relative manifest path")
        subparser.add_argument("--file", action="append", required=True, help="relative artifact path; repeat")
        _add_identity_arguments(subparser)
    extract = subparsers.add_parser("extract", help="safely extract the fixed fast-CI build bundle")
    extract.add_argument("--bundle", required=True)
    extract.add_argument("--destination", required=True)
    extract.add_argument("--expected-bundle-sha256", required=True)
    subparsers.choices["verify"].add_argument(
        "--expected-manifest-sha256", required=True,
        help="digest from a trusted producer job output, never from the artifact itself",
    )
    return parser


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "extract":
            print(extract_bundle(args.bundle, args.destination, args.expected_bundle_sha256))
            return 0
        roots = _parse_stdlib_roots(args.stdlib)
        identity = _identity(
            args.source_commit, args.run_id, args.run_attempt, args.producer_job, args.target,
            args.target_cpu, args.build_flag, args.expected_compiler_version, args.compiler,
            args.expected_runtime_version, args.runtime,
            args.stdlib_version, roots,
        )
        paths = sorted(args.file)
        if args.command == "create":
            digest = create_manifest(args.root, args.manifest, identity, paths)
            print(digest)
        else:
            digest = verify_manifest(args.root, args.manifest, args.expected_manifest_sha256,
                                     identity, paths)
            print(f"VERIFIED {digest}")
        return 0
    except (ManifestError, OSError, ValueError) as error:
        print(f"artifact manifest rejected: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
