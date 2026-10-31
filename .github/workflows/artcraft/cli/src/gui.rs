//! Graphical update bridge; only the verified pacman transaction is elevated.
use super::*;

pub(super) fn transaction(arguments: &[String]) -> Result<()> {
    ensure!(
        arguments
            .first()
            .is_some_and(|arg| matches!(arg.as_str(), "-U" | "-R")),
        "Unsupported graphical transaction"
    );
    let result = Process::new("/usr/bin/pkexec")
        .arg("/usr/bin/pacman")
        .arg("--noconfirm")
        .args(arguments)
        .stdin(Stdio::null())
        .output()
        .context("Could not start graphical authorization")?;
    ensure!(
        result.status.success(),
        "Package operation failed or authorization was cancelled: {}{}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );
    Ok(())
}

pub(super) fn catalog(name: &str) -> Result<()> {
    ensure!(
        !name.is_empty()
            && name
                .bytes()
                .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == b'-'),
        "Invalid package name"
    );
    let client = client()?;
    let catalog = catalog::load(&client, true)?;
    let remote = catalog
        .get(name)
        .context("No published native package for this application yet")?;
    let local = installed(name)?;
    let changed = match local {
        Some(ref version) => newer(&remote.version, version)?,
        None => true,
    };
    let version = upstream_version(&remote.version);
    let release = serde_json::json!({
        "tag": remote.release.tag_name,
        "version": version,
        "name": format!("{} {}", name, version),
        "published_at": null,
        "html_url": remote.release.html_url,
        "notes": "Native Arch Linux package published by zamkara/storytold. Installation requires system authorization.",
        "prerelease": false,
        "assets": []
    });
    println!(
        "{}",
        if changed {
            release
        } else {
            serde_json::Value::Null
        }
    );
    Ok(())
}

fn upstream_version(package: &str) -> &str {
    let upstream = package
        .rsplit_once('-')
        .map_or(package, |(version, _)| version);
    upstream.split(".r").next().unwrap_or(upstream)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn native_versions_hide_snapshot_suffixes_but_keep_prereleases() {
        assert_eq!(
            upstream_version("0.13.1.r20261031120000.gabcdef-2"),
            "0.13.1"
        );
        assert_eq!(
            upstream_version("0.13.1-rc.1.r20261031120000.gabcdef-1"),
            "0.13.1-rc.1"
        );
    }
    #[test]
    fn catalog_flags_do_not_accept_an_install_action() {
        assert!(Cli::try_parse_from(["artcraft", "-J", "figcraft"]).is_ok());
        assert!(Cli::try_parse_from(["artcraft", "-J", "figcraft", "-i"]).is_err());
    }
}
