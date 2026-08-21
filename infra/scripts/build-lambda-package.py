#!/usr/bin/env python3
"""Builds the two zip artifacts the Lambda functions deploy from. No Docker.

    python infra/scripts/build-lambda-package.py

Produces, in infra/build/:
  layer.zip - third-party dependencies, published as a Lambda layer and shared
              by all four functions. ~21 MB zipped / ~71 MB unzipped.
  app.zip   - this repo's own code (app/, alembic/, alembic.ini). Tiny, so a
              code-only deploy re-uploads kilobytes rather than the whole tree.

Why zip rather than a container image: Lambda zip functions cold-start faster
than image-based ones, Terraform uploads the artifact itself (so there is no
ECR repository, no `docker login`, and no chicken-and-egg "create the registry
before the functions" apply), and building needs nothing but Python - which
matters on Windows, where Docker Desktop is a heavyweight prerequisite for what
is otherwise a pip download.

The wheels are Linux wheels fetched *from whatever OS you run this on*: pip can
resolve for a target platform and Python version it isn't currently running,
provided every dependency publishes a matching wheel. --only-binary=:all: makes
that a hard requirement rather than a silent fallback to building from source,
which would produce Windows or macOS binaries that fail at import on Lambda with
a bare "invalid ELF header".
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
BUILD_DIR = REPO_ROOT / "infra" / "build"

# Must match `python_runtime` in infra/terraform/lambda.tf. The wheels are
# compiled for one CPython version (asyncpg ships
# protocol.cpython-312-x86_64-linux-gnu.so, not an abi3 wheel), so a runtime
# that disagrees with this fails at import, not at deploy.
TARGET_PYTHON = "3.12"

# Must match `architectures` in infra/terraform/lambda.tf.
#
# Several of these dependencies publish PEP 600 wheels (manylinux_2_28) and no
# legacy manylinux2014 wheel, so asking only for manylinux2014 silently finds
# "no matching distribution" for a package that publishes a perfectly good
# wheel. The Lambda python3.12 runtime is Amazon Linux 2023 (glibc 2.34), so any
# of these tags is loadable there.
TARGET_PLATFORMS = [
    "manylinux2014_x86_64",
    "manylinux_2_17_x86_64",
    "manylinux_2_28_x86_64",
    "manylinux_2_34_x86_64",
]

# A fixed timestamp for every zip entry. Without it the archive's hash changes
# on every build purely because mtimes moved, and Terraform would redeploy all
# four functions on every apply even when nothing changed.
FIXED_TIMESTAMP = (2000, 1, 1, 0, 0, 0)

EXCLUDED_DIR_NAMES = {"__pycache__", ".pytest_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}

# Binaries belonging to the machine doing the build, which must never reach a
# Linux Lambda. Their presence in the staging tree means pip built something
# from source locally instead of using a Linux wheel, so this is a hard error
# rather than a filter.
HOST_BINARY_SUFFIXES = {".exe", ".pyd", ".dll", ".dylib"}


def _log(message: str) -> None:
    print(f"==> {message}", flush=True)


def _iter_files(root: Path):
    """Every file under root, sorted, with caches skipped.

    Sorted because zip entry order is otherwise filesystem-dependent, which would
    defeat the reproducible-hash goal above.
    """
    for path in sorted(root.rglob("*"), key=lambda p: p.as_posix()):
        if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
            continue
        if path.is_file() and path.suffix not in EXCLUDED_SUFFIXES:
            yield path


def _write_zip(zip_path: Path, entries: list[tuple[Path, str]]) -> None:
    """Write a zip whose contents Lambda can actually read.

    Permissions are set explicitly rather than copied from disk: a file created
    on Windows carries no POSIX mode, and zipfile would record 0o600 - which on
    Lambda means the runtime user cannot read its own code.
    """
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source, arcname in entries:
            info = zipfile.ZipInfo(arcname, date_time=FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, source.read_bytes())


def build_layer() -> Path:
    """Dependencies, laid out the way a Lambda layer must be: under python/."""
    staging = BUILD_DIR / "layer-staging"
    if staging.exists():
        shutil.rmtree(staging)
    target = staging / "python"
    target.mkdir(parents=True)

    requirements = BACKEND / "requirements-lambda.txt"
    platform_args: list[str] = []
    for platform in TARGET_PLATFORMS:
        platform_args += ["--platform", platform]

    _log(f"Downloading Linux wheels for CPython {TARGET_PYTHON} (this needs network, not Docker)...")
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install",
            "--no-cache-dir",
            # Never compile from source: a source build here would produce
            # binaries for *this* machine, not for Lambda.
            "--only-binary=:all:",
            *platform_args,
            "--implementation", "cp",
            "--python-version", TARGET_PYTHON,
            "--target", str(target),
            "-r", str(requirements),
        ],
        check=True,
    )

    # pip generates console-script launchers for the *host* OS - on Windows,
    # actual .exe wrappers. They're unusable on Lambda (nothing invokes a CLI
    # there; the migration function calls Alembic's Python API), they bloat the
    # layer, and their bytes vary between runs, which would make the artifact
    # hash - and therefore every deploy - churn for no reason.
    scripts_dir = target / "bin"
    if scripts_dir.exists():
        _log(f"Dropping {len(list(scripts_dir.iterdir()))} host console-script launchers (python/bin/)")
        shutil.rmtree(scripts_dir)

    # C headers for building *against* these packages (greenlet ships one). They
    # are never loaded at runtime, and pip files them under a directory named
    # after whichever interpreter ran the build - so keeping them would make the
    # artifact differ between two machines that produced identical code.
    include_dir = target / "include"
    if include_dir.exists():
        _log("Dropping bundled C headers (python/include/) - build-host specific, unused at runtime")
        shutil.rmtree(include_dir)

    # RECORD is pip's uninstall manifest: it lists every installed file with its
    # hash, including the launchers just deleted, so its bytes differ per build.
    # Nothing reads it at runtime (importlib.metadata.version() reads METADATA,
    # which stays), and dropping it is what makes the layer byte-reproducible.
    records = [p for p in target.glob("*.dist-info/RECORD")]
    for record in records:
        record.unlink()
    if records:
        _log(f"Dropping {len(records)} dist-info RECORD manifests (installer metadata, unused at runtime)")

    stray = [p for p in _iter_files(staging) if p.suffix.lower() in HOST_BINARY_SUFFIXES]
    if stray:
        raise SystemExit(
            "error: host-platform binaries in the dependency tree, which would fail to load on Lambda:\n  "
            + "\n  ".join(str(p.relative_to(staging)) for p in stray[:10])
            + "\nThis means pip did not use a Linux wheel for one of the pins."
        )

    entries = [(p, p.relative_to(staging).as_posix()) for p in _iter_files(staging)]
    zip_path = BUILD_DIR / "layer.zip"
    _log(f"Packing {len(entries)} dependency files -> {zip_path.name}")
    _write_zip(zip_path, entries)
    shutil.rmtree(staging)
    return zip_path


def build_app() -> Path:
    """This repo's own code. alembic/ and alembic.ini ride along because the
    migration function runs `alembic upgrade head` from the same artifact."""
    entries: list[tuple[Path, str]] = []
    for relative in ("app", "alembic"):
        source_root = BACKEND / relative
        entries += [(p, p.relative_to(BACKEND).as_posix()) for p in _iter_files(source_root)]
    entries.append((BACKEND / "alembic.ini", "alembic.ini"))

    # A stray .env inside the artifact would silently override the Lambda
    # environment variables Terraform sets, since pydantic reads it relative to
    # the working directory - which on Lambda is the unpacked artifact root.
    assert not any(name == ".env" for _, name in entries), "refusing to package a .env file"

    zip_path = BUILD_DIR / "app.zip"
    _log(f"Packing {len(entries)} application files -> {zip_path.name}")
    _write_zip(zip_path, entries)
    return zip_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app-only", action="store_true",
                        help="Rebuild only app.zip. Valid when no dependency pin changed; "
                             "layer.zip must already exist.")
    args = parser.parse_args()

    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    if args.app_only:
        if not (BUILD_DIR / "layer.zip").exists():
            print("error: --app-only given but infra/build/layer.zip doesn't exist yet.", file=sys.stderr)
            return 1
    else:
        build_layer()
    build_app()

    _log("Artifacts ready:")
    for artifact in sorted(BUILD_DIR.glob("*.zip")):
        print(f"    {artifact.relative_to(REPO_ROOT).as_posix()}  ({artifact.stat().st_size / 1024 / 1024:.1f} MB)")
    print()
    print("Next: terraform -chdir=infra/terraform apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
