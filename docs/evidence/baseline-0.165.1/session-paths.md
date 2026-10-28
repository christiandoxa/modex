# Session path joining

The production `session list` path and path-query output were compared with
the checksum-pinned Linux 0.165.1 executable in isolated homes. A shared home
ending in one slash now joins `sessions` without adding a second separator;
two trailing slashes and an internal repeated separator retain the reference's
behavior. The same synthetic cases matched the historical 0.439.2 executable.
The native path join also checks `/` as the root.

This does not qualify state locking, profile filtering, path security in every
filesystem configuration, or any non-Linux release target.
