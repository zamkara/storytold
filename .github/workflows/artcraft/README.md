# Storytold native application suite

The workflow checks all registered upstream applications and Artcraft's own Rust source
at 20:17 UTC / 03:17 Asia/Jakarta every day. Manual dispatch and relevant pushes
also run the complete pipeline. Pull requests run validation.

All registered native Arch packages and the Artcraft manager are built independently in disposable Arch Linux
containers. Unchanged upstream commits and packaging inputs skip compilation.
Failed builds never advance the published checkpoints. Source snapshots, fonts,
and lockfiles come from pinned upstream revisions; no upstream repository or
vendored dependencies are committed here.

One final job publishes one complete suite release only after all build jobs
succeed. It includes Artcraft, every registered app package, the Artcraft binary,
installer, per-app PKGBUILD/SRCINFO/state/changelog files, suite.json, and shared
SHA256SUMS. Unchanged verified packages are carried forward from earlier releases.
The complete asset set is uploaded and checked as a draft before it becomes
public and latest. A partial suite is never published.

```sh
curl -fsSL https://github.com/zamkara/storytold/releases/latest/download/install.sh | bash
artcraft -ia
```

Artcraft discovers available packages from verified release metadata. The workflow
registry in apps.json declares build targets and is not embedded in the manager.
The TUI initially shows installed apps; Sync discovers the published catalog.
Pacman owns installations and upgrades. CLI confirmations read from the terminal;
the TUI provides transaction confirmation and masked authentication prompts.

Full original upstream changelogs are separate APP.CHANGELOG.md assets. Release
notes link them and include original excerpts within GitHub's body-size limit.
Snapshots use upstream-version.rCOMMITTIMESTAMP.gCOMMIT and packaging changes
increment pkgrel. Builds, caches and source archives remain disposable runner
files, not repository content. The root contains LICENSE, .github, and the repository README.

See [CLI usage](cli/README.md).

FigCraft is built from `storytold/figcraft` as a native Arch Linux package, including
its CLI, upstream desktop entry, icons, MIME associations and AppStream metadata.
The shared builder pins its source revision and upstream font revision, verifies
source checksums, and publishes it only as part of a complete validated suite.

SolidCraft is the community parametric 3D CAD application from
`tangency-labs/solidcraft`. Its dedicated source recipe preserves the upstream
application ID, desktop and MIME integration, exported icons, CLI compatibility
shim and attribution notices. AniCraft is not registered while its repository
has no source to build.


ArtCraft Launcher is also built from `storytold/craft-launcher`, without source
changes, as `artcraft-launcher`. It has no extra `-cli` binary and does not replace
`artcraft`. Its fonts, asset attributions and restricted brand license are shipped
with the package. Launch it with `artcraft-launcher` after installing it through
`artcraft -i artcraft-launcher`.

The upstream graphical launcher still uses upstream's catalog and install policy.
It detects our installed packages through pacman but does not drive our release
catalog. Use `artcraft` for this builder's installations and upgrades. Do not treat
these two frontends as interchangeable. A modified launcher would require separate
branding under upstream's brand license; this package preserves the original.

## Native in-app updates

The thirteen Craft editors using `craft-update`, plus SolidCraft's separate updater,
use `/usr/lib/artcraft/package-bridge` for packaged Linux copies. Checks ask for
packages actually published in our complete suite; they never offer an upstream
binary that our builder has not released. Installation downloads and verifies the
package without elevated rights, then requests polkit authorization for pacman.
Cancellation or installation failure stays an error in the original update dialog.
The existing application restart and unsaved-work handling are retained. Nothing
writes a replacement executable directly into `/usr/bin`.

Upgrade the manager first (`artcraft -U`), then the installed apps (`artcraft -u`)
to acquire this integration. Older installed app binaries cannot be repaired by a
manager-only update. New app packages depend on the manager's
`artcraft-package-bridge` capability. Initial install and update remain explicitly
user-triggered; no background privileged updater is installed.

The locked Cargo dependency revision and lockfile are preserved. Each build applies
a deterministic, fingerprinted transformation only to that job's private Cargo
checkout. A source layout the transformation does not recognize fails the build.
The transformation is downloaded from the exact builder commit and SHA-256 checked
as a PKGBUILD source. SolidCraft is transformed in the disposable extracted source.
No upstream source is tracked in this repository.

ArtCraft Studio and ArtCraft-X have no upstream in-app updater in the inspected
source; update them with `artcraft -u`. The unchanged upstream graphical launcher's
own updater is also outside this bridge; update its package with
`artcraft -u artcraft-launcher`.
