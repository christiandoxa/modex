"""Regression for empty managed roots in the Super dry-run path."""

import shlex
from pathlib import Path
import unittest

from test_super_dry_run_01651 import (
    MODEX,
    OPTIONAL_TOOL_FIXTURE,
    run_dry_run,
    write_codebase_version,
    write_optional_tool,
    write_rtk_version,
    write_tool,
)


def write_marked_tool(path, marker, version):
    path.write_text(
        "#!/bin/sh\n"
        f"printf 'executed\\n' > {shlex.quote(str(marker))}\n"
        f"printf '{version}\\n'\n"
    )
    path.chmod(0o700)


class SuperEmptyManagedRoot01661Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not OPTIONAL_TOOL_FIXTURE.is_file() or OPTIONAL_TOOL_FIXTURE.stat().st_mode & 0o111 == 0:
            raise AssertionError("Build the native optional-tool fixture with make unit-build")

    def test_empty_override_does_not_probe_cwd_codebase_memory(self):
        def prepare(root):
            write_tool(
                root / "workspace/codebase-memory-mcp",
                root / "cwd-codebase-memory-executed",
            )

        result, before, after = run_dry_run(
            MODEX,
            "modex",
            prepare,
            environment=lambda root: {"PRODEX_OPTIMIZERS_HOME": ""},
        )

        self.assertEqual((result.returncode, result.stderr), (0, b""), result.stderr)
        self.assertIn(
            b"codebase-memory-mcp: skipped (codebase-memory-mcp was not found in managed roots or PATH)",
            result.stdout,
        )
        self.assertEqual(after, before, "the empty override must not execute a cwd tool")

    def test_empty_xdg_data_home_does_not_probe_root_level_codebase_memory(self):
        def prepare(root):
            xdg_root = root / "xdg-tools"
            xdg_root.mkdir(mode=0o700)
            binary = xdg_root / "codebase-memory-mcp"
            write_optional_tool(binary)
            write_codebase_version(root, binary, "codebase-memory-mcp 0.12.1")

        result, before, after = run_dry_run(
            MODEX,
            "modex",
            prepare,
            environment=lambda root: {"XDG_DATA_HOME": ""},
            extra_binaries=(OPTIONAL_TOOL_FIXTURE,),
            extra_binds=lambda root: ((root / "xdg-tools", "/prodex-optimizers"),),
        )

        self.assertEqual((result.returncode, result.stderr), (0, b""), result.stderr)
        self.assertIn(
            b"codebase-memory-mcp: skipped (codebase-memory-mcp was not found in managed roots or PATH)",
            result.stdout,
        )
        self.assertEqual(after, before, "empty XDG_DATA_HOME must not map to /prodex-optimizers")

    def test_dot_component_symlinked_optimizer_root_fails_closed(self):
        def prepare(root):
            target = root / "optimizer-target"
            target.mkdir(mode=0o700)
            write_optional_tool(target / "rtk")
            (root / "managed-root-link").symlink_to(target, target_is_directory=True)

        result, before, after = run_dry_run(
            MODEX,
            "modex",
            prepare,
            environment=lambda root: {
                "PRODEX_OPTIMIZERS_HOME": str(root / "managed-root-link") + "/."
            },
            extra_binaries=(OPTIONAL_TOOL_FIXTURE,),
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn(b"cannot report installed optional tools yet", result.stderr)
        self.assertEqual(after, before)

    def test_setuid_and_setgid_managed_tools_are_not_probed(self):
        cases = (
            ("setuid RTK", "rtk", 0o4700, "rtk 1.1.0"),
            ("setgid RTK", "rtk", 0o2700, "rtk 1.1.0"),
            ("setuid Codebase Memory", "codebase-memory-mcp", 0o4700, "codebase-memory-mcp 0.12.1"),
            ("setgid Codebase Memory", "codebase-memory-mcp", 0o2700, "codebase-memory-mcp 0.12.1"),
        )
        for label, name, mode, version in cases:
            with self.subTest(label=label):
                def prepare(root):
                    managed = root / "home/.local/share/prodex-optimizers"
                    managed.mkdir(parents=True, mode=0o700)
                    binary = managed / name
                    write_optional_tool(binary)
                    binary.chmod(mode)
                    self.assertEqual(binary.stat().st_mode & 0o6000, mode & 0o6000)
                    if name == "rtk":
                        write_rtk_version(root, version, managed=True)
                    else:
                        write_codebase_version(root, binary, version)

                result, before, after = run_dry_run(
                    MODEX,
                    "modex",
                    prepare,
                    extra_binaries=(OPTIONAL_TOOL_FIXTURE,),
                )

                if name == "rtk":
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(b"cannot report installed optional tools yet", result.stderr)
                else:
                    self.assertEqual((result.returncode, result.stderr), (0, b""), result.stderr)
                    self.assertIn(
                        b"codebase-memory-mcp: skipped (managed codebase-memory-mcp root or executable is unsafe)",
                        result.stdout,
                    )
                self.assertEqual(after, before)

    def test_managed_probe_rejects_other_principal_write_access(self):
        shell = Path("/bin/sh").resolve()
        cases = (
            ("private root", 0o700, 0o700, 0o700, True),
            ("writable root", 0o700, 0o777, 0o700, False),
            ("writable ancestor", 0o777, 0o700, 0o700, False),
            ("writable executable", 0o700, 0o700, 0o777, False),
        )
        for tool, version in (
            ("rtk", "rtk 1.1.0"),
            ("codebase-memory-mcp", "codebase-memory-mcp 0.12.1"),
        ):
            for label, parent_mode, root_mode, executable_mode, should_run in cases:
                with self.subTest(tool=tool, label=label):
                    def prepare(root):
                        parent = root / "managed-parent"
                        managed = parent / "managed-tools"
                        parent.mkdir(mode=0o700)
                        managed.mkdir(mode=0o700)
                        parent.chmod(parent_mode)
                        managed.chmod(root_mode)
                        write_marked_tool(
                            managed / tool,
                            root / f"{tool}-executed",
                            version,
                        )
                        (managed / tool).chmod(executable_mode)

                    result, before, after = run_dry_run(
                        MODEX,
                        "modex",
                        prepare,
                        environment=lambda root: {
                            "PRODEX_OPTIMIZERS_HOME": str(root / "managed-parent/managed-tools")
                        },
                        extra_binaries=(shell,),
                        extra_binds=lambda root: ((shell, "/bin/sh"),),
                    )

                    if should_run:
                        self.assertEqual((result.returncode, result.stderr), (0, b""), result.stderr)
                        self.assertIn(
                            b"rtk: resolved (activation deferred until launch)"
                            if tool == "rtk"
                            else b"codebase-memory-mcp: resolved (activation deferred until launch)",
                            result.stdout,
                        )
                        marker = f"{tool}-executed"
                        self.assertIn(marker, after)
                        self.assertEqual(set(after) - set(before), {marker})
                    else:
                        if tool == "rtk":
                            self.assertEqual(result.returncode, 1)
                            self.assertIn(b"cannot report installed optional tools yet", result.stderr)
                        else:
                            self.assertEqual((result.returncode, result.stderr), (0, b""), result.stderr)
                            self.assertIn(
                                b"codebase-memory-mcp: skipped (managed codebase-memory-mcp root or executable is unsafe)",
                                result.stdout,
                            )
                        self.assertNotIn(f"{tool}-executed", after)
                        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
