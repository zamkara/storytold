"""Patch only the locked craft-update dependency in this job's private Cargo checkout.

Cargo still resolves the original locked revision. The deterministic transformation is part
of the recipe fingerprint; an unknown source layout fails the build instead of silently
shipping a broken updater. No dependency revision or lockfile is changed.
"""
import argparse,json,os,pathlib,re,subprocess


def inject(source,pattern,code):
    matches=list(re.finditer(pattern,source,re.S))
    if len(matches)!=1:raise ValueError('Unsupported craft-update source layout: '+pattern)
    end=matches[0].end()
    return source[:end]+code+source[end:]


def transform(lib,updater):
    check='''
    #[cfg(target_os = "linux")]
    if let (Some(helper), Some(package)) = (option_env!("ARTCRAFT_PACKAGE_BRIDGE"), option_env!("ARTCRAFT_PACKAGE_NAME")) {
        let result = std::process::Command::new(helper).args(["check", package]).output()
            .map_err(|e| format!("could not check native package updates: {e}"))?;
        if !result.status.success() {
            return Err(String::from_utf8_lossy(&result.stderr).trim().to_string());
        }
        return serde_json::from_slice(&result.stdout).map_err(|e| format!("invalid native release: {e}"));
    }
'''
    install='''
    #[cfg(target_os = "linux")]
    if let (Some(helper), Some(package)) = (option_env!("ARTCRAFT_PACKAGE_BRIDGE"), option_env!("ARTCRAFT_PACKAGE_NAME")) {
        stop.check()?;
        last()?;
        phase(JobPhase::Installing);
        let result = std::process::Command::new(helper).args(["install", package]).output()
            .map_err(|e| format!("could not start native package update: {e}"))?;
        if !result.status.success() {
            return Err(String::from_utf8_lossy(&result.stderr).trim().to_string());
        }
        let exe = std::env::current_exe().map_err(|e| format!("could not locate application: {e}"))?;
        mark_installed(paths, release);
        return relaunch_after_exit(app, std::process::id(), &[exe.as_os_str()]);
    }
'''
    lib=inject(lib,r'pub fn check_for_update\([^{}]*?\) -> Result<Option<Release>, String> \{',check)
    updater=inject(updater,r'pub fn update\([^{}]*?\) -> Result<\(\), String> \{',install)
    return lib,updater


def transform_solid(update,install):
    update=inject(update,r'fn fetch_latest\([^{}]*?\) -> Result<Release, FetchError> \{','''
    #[cfg(target_os = "linux")]
    if let (Some(helper), Some(package)) = (option_env!("ARTCRAFT_PACKAGE_BRIDGE"), option_env!("ARTCRAFT_PACKAGE_NAME")) {
        let result = std::process::Command::new(helper).args(["check", package]).output()
            .map_err(|e| FetchError::Failed(format!("native package check: {e}")))?;
        if !result.status.success() {
            return Err(FetchError::Failed(String::from_utf8_lossy(&result.stderr).trim().to_string()));
        }
        let value: serde_json::Value = serde_json::from_slice(&result.stdout)
            .map_err(|e| FetchError::Failed(format!("native release metadata: {e}")))?;
        let version = value.get("version").and_then(serde_json::Value::as_str).unwrap_or(current_version());
        return Ok(Release { tag: format!("v{version}"), name: format!("SolidCraft {version}"),
            notes: value.get("notes").and_then(serde_json::Value::as_str).unwrap_or("").to_string(),
            page: value.get("html_url").and_then(serde_json::Value::as_str).unwrap_or("https://github.com/zamkara/storytold/releases/latest").to_string(),
            assets: Vec::new() });
    }
''')
    update=inject(update,r'pub fn install_method\([^{}]*?\) -> Option<install::Method> \{','''
    #[cfg(target_os = "linux")]
    if option_env!("ARTCRAFT_PACKAGE_BRIDGE").is_some() {
        return std::env::current_exe().ok().map(install::Method::Exe);
    }
''')
    install=inject(install,r'pub fn run\([^{}]*?\) -> Result<Outcome, String> \{','''
    #[cfg(target_os = "linux")]
    if let (Some(helper), Some(package)) = (option_env!("ARTCRAFT_PACKAGE_BRIDGE"), option_env!("ARTCRAFT_PACKAGE_NAME")) {
        if progress.cancel.load(Ordering::Relaxed) { return Err("cancelled".into()); }
        let result = std::process::Command::new(helper).args(["install", package]).output()
            .map_err(|e| format!("native package update: {e}"))?;
        if !result.status.success() { return Err(String::from_utf8_lossy(&result.stderr).trim().to_string()); }
        return std::env::current_exe().map(Outcome::Restart).map_err(|e| format!("application path: {e}"));
    }
''')
    return update,install


def main():
    p=argparse.ArgumentParser();p.add_argument('--required',action='store_true');p.add_argument('--solidcraft',action='store_true');args=p.parse_args()
    if args.solidcraft:
        paths=[pathlib.Path('crates/ui-egui/src/update.rs'),pathlib.Path('crates/ui-egui/src/update/install.rs')]
        for path,text in zip(paths,transform_solid(*(path.read_text() for path in paths))):path.write_text(text)
        print('Integrated SolidCraft package updater');return
    data=json.loads(subprocess.check_output(['cargo','metadata','--locked','--format-version=1'],text=True))
    packages=[item for item in data['packages'] if item['name']=='craft-update']
    if not packages:
        if args.required:raise SystemExit('No supported craft-update dependency; refusing to ship an unintegrated updater')
        print('No shared craft-update dependency');return
    home=pathlib.Path(os.environ['CARGO_HOME']).resolve()
    for item in packages:
        root=pathlib.Path(item['manifest_path']).resolve().parent
        if not root.is_relative_to(home/'git/checkouts'):
            raise SystemExit('Updater must come from a pinned checkout in this job Cargo home')
        originals=[]
        for name in ['lib.rs','self_update.rs']:
            path=root/'src'/name
            # Reset our previous cached transformation, retaining the locked Git revision.
            checkout=pathlib.Path(subprocess.check_output(
                ['git','-C',str(root),'rev-parse','--show-toplevel'],text=True).strip())
            relative=path.relative_to(checkout)
            original=subprocess.check_output(
                ['git','-C',str(checkout),'show','HEAD:'+relative.as_posix()],text=True)
            originals.append(original)
        changed=transform(*originals)
        for name,text in zip(['lib.rs','self_update.rs'],changed):
            (root/'src'/name).write_text(text)
        print('Integrated locked updater:',item['source'])

if __name__=='__main__':main()
