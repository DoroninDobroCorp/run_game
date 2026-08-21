# Remote SSH Python CI

This is an alternative to the blocked GitHub Actions account for the portable
part of the release gate. It runs static analysis, Python compilation, the
five-part privacy/history audit and the complete synthetic Python suite on an
SSH-accessible Linux or macOS host. It does **not** build Swift, execute iOS
tests, access the private fixture, or replace the physical-iPhone smoke.

## One-time host requirements

- A clean checkout of the exact release commit.
- Python 3.8+ with the `venv` module and outbound access to PyPI for the pinned
  development dependencies.
- Git and Bash. No Apple credentials, private bundle or tester data are copied.

## Exact run

From the repository root on the remote host:

```bash
git fetch --all --prune
git checkout --detach <full-release-commit>
tools/r02_remote_python_ci.sh "$PWD"
```

For a normal SSH workflow, transfer only the public checkout (or let the host
clone via its own deploy key). Do not `rsync` `research/r02/local/`, iOS
DerivedData, simulator folders, GPX, signing certificates or `.env` files.

Save the complete terminal log alongside the release evidence. A zero exit code
is `PASS_REMOTE_PYTHON_ONLY`; it is evidence for the listed portable gates, not
a green iOS CI run.

## What still needs a Mac or iPhone

| Gate | Why the SSH Python host cannot replace it |
| :--- | :--- |
| Swift runtime / UI tests | Requires Xcode, an iOS runtime and a functioning CoreSimulator service. |
| App signing and installation | Requires the QA Apple team, provisioning and a physical iPhone. |
| GPS, background, lock-screen audio | These are device/OS integration behaviors, not Python behavior. |
| Private preflight and handoff manifest | Requires the authoritative private five-file bundle. |

Use a second Mac, self-hosted macOS runner, Xcode Cloud, or a repaired local
Mac for those Apple-specific gates. The GitHub billing lock is therefore
avoidable for the portable checks, but not with a generic Linux SSH server.
