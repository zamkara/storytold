import importlib.util,json,pathlib,subprocess,tempfile,unittest
from unittest.mock import patch
import patch_updater,prepare,registry
HERE=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('package_bridge',HERE/'package-bridge.py')
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)

class UpdaterTests(unittest.TestCase):
    def test_unknown_dependency_layout_fails_closed(self):
        with self.assertRaises(ValueError):patch_updater.transform('renamed API','different updater')

    def test_bridge_precedes_standalone_download_and_replace(self):
        lib='pub fn check_for_update(app: &App, http: &Http, current_version: &str) -> Result<Option<Release>, String> {\nORIGINAL_CHECK\n}'
        updater='pub fn update(app: &App, install: &Install, release: &Release, platform: Platform, http: &Http, paths: &Paths, stop: &Stop, phase: &mut dyn FnMut(JobPhase), last: &dyn Fn() -> Result<(), String>, running_version: Option<&str>) -> Result<(), String> {\nORIGINAL_REPLACE\n}'
        lib,updater=patch_updater.transform(lib,updater)
        self.assertLess(lib.index('ARTCRAFT_PACKAGE_BRIDGE'),lib.index('ORIGINAL_CHECK'))
        self.assertLess(updater.index('"install", package'),updater.index('ORIGINAL_REPLACE'))
        self.assertLess(updater.index('!result.status.success()'),updater.index('mark_installed'))
        self.assertIn('relaunch_after_exit',updater)

    def test_restart_return_type_starts_the_helper(self):
        lib='pub fn check_for_update(app: &App, http: &Http, current_version: &str) -> Result<Option<Release>, String> {\nORIGINAL_CHECK\n}'
        updater='fn relaunch_after_exit(app: &App, pid: u32, command: &[&std::ffi::OsStr]) -> Restart {\nORIGINAL_RESTART\n}\npub fn update(app: &App, install: &Install, release: &Release, platform: Platform, http: &Http, paths: &Paths, stop: &Stop, phase: &mut dyn FnMut(JobPhase), last: &dyn Fn() -> Result<(), String>, running_version: Option<&str>) -> Result<(), String> {\nORIGINAL_REPLACE\n}'
        _,updater=patch_updater.transform(lib,updater)
        self.assertIn('return relaunch_after_exit(app, std::process::id(), &[exe.as_os_str()]).start();',updater)

    def test_cancelled_authentication_does_not_report_success(self):
        with patch.object(bridge.subprocess,'run',return_value=subprocess.CompletedProcess([],126,'','Authorization cancelled')):
            with self.assertRaisesRegex(RuntimeError,'Authorization cancelled'):bridge.run(['artcraft','-u','figcraft'])

    def test_no_native_update_never_runs_pacman(self):
        calls=[]
        def run(command,timeout=900):
            calls.append(command)
            return 'null' if '-J' in command else 'figcraft 0.13.1-1'
        with patch('sys.argv',['bridge','install','figcraft']),patch.object(bridge.os,'geteuid',return_value=1000),patch.object(bridge,'run',run):
            with self.assertRaisesRegex(RuntimeError,'No newer'):bridge.main()
        self.assertFalse(any('-u' in cmd for cmd in calls))

    def test_launcher_is_separate_from_manager_without_fake_cli(self):
        config=registry.load_apps()['artcraft-launcher'];sha='a'*40
        def api(path):
            if path.endswith('/commits/main'):return {'sha':sha,'commit':{'committer':{'date':'2026-10-31T00:00:00Z'}}}
            return {'default_branch':'main'}
        def content(repo,path,sha):
            if path=='Cargo.toml':return '[workspace.package]\nversion="0.11.1"\n'
            return ''
        with tempfile.TemporaryDirectory() as folder,patch('sys.argv',['prepare.py','artcraft-launcher','--directory',folder]),patch.object(prepare,'api',api),patch.object(prepare,'content',content),patch.object(prepare,'previous',return_value=None),patch.object(prepare,'download_archive',return_value=('source.tar.gz::https://example.com/source','c'*64)),patch.object(prepare,'notes',return_value='Notes'),patch.object(prepare,'output'):
            prepare.main();recipe=(pathlib.Path(folder)/'PKGBUILD').read_text()
            self.assertIn('pkgname=artcraft-launcher',recipe)
            self.assertIn('ARTCRAFT_LAUNCHER_BUILD_SHA',recipe)
            self.assertNotIn('artcraft-launcher-cli',recipe)
            self.assertNotIn('ARTCRAFT_PACKAGE_BRIDGE',recipe)
            self.assertIn('LICENSE-brand.txt',recipe)
            subprocess.run(['bash','-n',str(pathlib.Path(folder)/'PKGBUILD')],check=True)

    def test_bridge_validates_install_outcome_before_success(self):
        release=json.dumps({'version':'0.13.1'})
        answers=iter(['figcraft 0.12.1-1',release,'installed','null'])
        with patch('sys.argv',['bridge','install','figcraft']),patch.object(bridge.os,'geteuid',return_value=1000),patch.object(bridge,'run',side_effect=lambda *a:next(answers)) as run:
            bridge.main()
            self.assertIn(['/usr/bin/artcraft','-u','figcraft'],[c.args[0] for c in run.call_args_list])

    def test_bridge_rejects_root_and_invalid_names(self):
        with patch('sys.argv',['bridge','install','figcraft']),patch.object(bridge.os,'geteuid',return_value=0):
            with self.assertRaisesRegex(RuntimeError,'normal user'):bridge.main()
        with patch('sys.argv',['bridge','install','../../other']):
            with self.assertRaisesRegex(ValueError,'package name'):bridge.main()

    def test_private_git_checkout_patch_is_repeatable_without_changing_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            home=pathlib.Path(directory)
            repo=home/'git/checkouts/craft-libs/locked';root=repo/'crates/update';(root/'src').mkdir(parents=True)
            (root/'Cargo.toml').write_text('[package]\nname="craft-update"\nversion="0.1.0"\n')
            (root/'src/lib.rs').write_text('pub fn check_for_update(app: &App, http: &Http, v: &str) -> Result<Option<Release>, String> { original() }')
            (root/'src/self_update.rs').write_text('pub fn update(app: &App) -> Result<(), String> { original() }')
            (repo/'Cargo.lock').write_text('locked revision stays intact\n')
            for args in [['init','-q'],['add','.'],['-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','Fixture']]:
                subprocess.run(['git','-C',str(repo),*args],check=True)
            real=patch_updater.subprocess.check_output
            def command(args,**kwargs):
                if args[0]=='cargo':return json.dumps({'packages':[{'name':'craft-update','manifest_path':str(root/'Cargo.toml'),'source':'git+https://github.com/storytold/craft-libs#locked'}]})
                return real(args,**kwargs)
            with patch('sys.argv',['patch_updater','--required']),patch.dict('os.environ',{'CARGO_HOME':str(home)}),patch.object(patch_updater.subprocess,'check_output',command),patch.object(patch_updater,'invalidate_updater_cache') as invalidate:
                patch_updater.main();first=(root/'src/lib.rs').read_text()
                patch_updater.main();self.assertEqual((root/'src/lib.rs').read_text(),first)
                self.assertEqual(invalidate.call_count,2)
            self.assertEqual((repo/'Cargo.lock').read_text(),'locked revision stays intact\n')

    def test_cached_git_dependency_is_recompiled_after_updater_patch(self):
        import contextlib,os,shutil
        if not shutil.which('cargo'):self.skipTest('Cargo is needed for the compiled-cache regression')
        with tempfile.TemporaryDirectory() as directory:
            base=pathlib.Path(directory);repo=base/'dependency';app=base/'application'
            for path in [repo/'src',app/'src']:path.mkdir(parents=True)
            (repo/'Cargo.toml').write_text('[package]\nname="craft-update"\nversion="0.1.0"\nedition="2021"\n')
            (repo/'src/lib.rs').write_text('pub fn bridge() -> &\'static str { "unpatched" }\n')
            for args in [['init','-q'],['add','.'],['-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','Fixture']]:
                subprocess.run(['git','-C',str(repo),*args],check=True)
            revision=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
            (app/'Cargo.toml').write_text('[package]\nname="cache-probe"\nversion="0.1.0"\nedition="2021"\n[dependencies]\ncraft-update={git="'+repo.as_uri()+'",rev="'+revision+'"}\n')
            (app/'src/main.rs').write_text('fn main() { println!("{}", craft_update::bridge()); }\n')
            env={'CARGO_HOME':str(base/'cargo'),'CARGO_TARGET_DIR':str(base/'target'),'ARTCRAFT_PACKAGE_BRIDGE':'/usr/lib/artcraft/package-bridge'}
            with patch.dict(os.environ,env),contextlib.chdir(app):
                # First populate the exact kind of immutable Git dependency cache used by CI.
                subprocess.run(['cargo','build','--release','--quiet'],check=True,capture_output=True)
                binary=base/'target/release/cache-probe'
                self.assertEqual(subprocess.check_output([str(binary)],text=True).strip(),'unpatched')
                checkout=next((base/'cargo/git/checkouts').glob('*/*/src/lib.rs'))
                checkout.write_text('pub fn bridge() -> &\'static str { option_env!("ARTCRAFT_PACKAGE_BRIDGE").unwrap_or("unpatched") }\n')
                subprocess.run(['cargo','build','--release','--locked','--offline','--quiet'],check=True,capture_output=True)
                before=subprocess.check_output([str(binary)],text=True).strip()
                print('Cached Git dependency before invalidation:',before)
                patch_updater.invalidate_updater_cache()
                subprocess.run(['cargo','build','--release','--locked','--offline','--quiet'],check=True,capture_output=True)
                after=subprocess.check_output([str(binary)],text=True).strip()
                print('Cached Git dependency after invalidation:',after)
                self.assertEqual(after,env['ARTCRAFT_PACKAGE_BRIDGE'])
                self.assertIn(env['ARTCRAFT_PACKAGE_BRIDGE'].encode(),binary.read_bytes())
