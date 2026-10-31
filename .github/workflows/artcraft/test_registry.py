import json,pathlib,tempfile,unittest
from unittest.mock import patch
import registry,prepare
class RegistryTests(unittest.TestCase):
    def test_registry_contains_all_sixteen_upstream_apps(self):
        apps=registry.load_apps()
        self.assertEqual(len(apps),16)
        self.assertNotIn('artcraft',apps)
        self.assertEqual(apps['artcraft-studio']['repo'],'storytold/artcraft')
        self.assertNotIn('artcraft-launcher',apps)
        self.assertEqual(apps['figcraft']['repo'],'storytold/figcraft')
    def test_manager_name_is_reserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path=pathlib.Path(folder)/'apps.json';path.write_text(json.dumps({'artcraft':{'repo':'storytold/artcraft','description':'App'}}))
            with self.assertRaises(ValueError):registry.load_apps(path)
    def test_tauri_version_comes_from_upstream_app_configuration(self):
        with patch.object(prepare,'content',return_value=json.dumps({'version':'0.42.0','identifier':'ai.artcraft.app'})):
            version,app_id,fonts=prepare.build_metadata({'kind':'tauri','crate_path':'crates/desktop/artcraft'},{'workspace':{}},'storytold/artcraft','commit')
            self.assertEqual((version,app_id,fonts),('0.42.0','ai.artcraft.app',''))
    def test_recipes_support_tauri_without_a_cli_binary(self):
        for name in ['artcraft-studio','artcraftx']:
            config=registry.load_apps()[name];repo=config['repo'];sha='a'*40
            def api(path):
                if path=='repos/'+repo:return {'default_branch':'main'}
                if path=='repos/'+repo+'/commits/main':return {'sha':sha,'commit':{'committer':{'date':'2026-10-10T00:00:00Z'}}}
                raise AssertionError(path)
            def content(repo,path,sha):
                if path=='Cargo.toml':return '[workspace.package]\nversion="0.1.3"\n'
                if path.endswith('tauri.conf.json'):return json.dumps({'version':'0.42.0','identifier':'ai.artcraft.app'})
                return ''
            with tempfile.TemporaryDirectory() as folder,patch('sys.argv',['prepare.py',name,'--directory',folder]),patch.object(prepare,'api',api),patch.object(prepare,'content',content),patch.object(prepare,'previous',return_value=None),patch.object(prepare,'download_archive',return_value=('source.tar.gz::https://example.com/source','b'*64)),patch.object(prepare,'notes',return_value='Exact upstream notes'),patch.object(prepare,'output'):
                prepare.main();recipe=(pathlib.Path(folder)/'PKGBUILD').read_text()
                self.assertNotIn('usr/bin/'+name+'-cli',recipe)
                self.assertIn(repo.split('/')[-1]+'-$_commit',recipe)
                import subprocess,re
                self.assertFalse(set(re.findall(r'@[A-Z_]+@',recipe)) - {'@VERSION@','@DATE@'})
                subprocess.run(['bash','-n',str(pathlib.Path(folder)/'PKGBUILD')],check=True)
                if config.get('kind')=='tauri':
                    self.assertIn('npm ci',recipe);self.assertIn('tauri/custom-protocol',recipe)
                    self.assertIn('nx run artcraft:build',recipe);self.assertIn('--allow-git=all',recipe)

    def test_figcraft_recipe_preserves_native_cli_fonts_and_desktop_integration(self):
        sha='a'*40;fonts='b'*40
        def api(path):
            if path=='repos/storytold/figcraft':return {'default_branch':'main'}
            if path=='repos/storytold/figcraft/commits/main':return {'sha':sha,'commit':{'committer':{'date':'2026-10-15T00:00:00Z'}}}
            raise AssertionError(path)
        def content(repo,path,commit):
            self.assertEqual(commit,sha)
            if path=='Cargo.toml':return '[workspace.package]\nversion="0.6.0"\n'
            if path=='.github/workflows/release.yml':return 'repository: storytold/craft-fonts\nCRAFT_FONTS_REF: '+fonts
            if path=='packaging/linux/package.sh':return 'cargo build --release --locked'
            raise AssertionError(path)
        with tempfile.TemporaryDirectory() as folder,patch('sys.argv',['prepare.py','figcraft','--directory',folder]),patch.object(prepare,'api',api),patch.object(prepare,'content',content),patch.object(prepare,'previous',return_value=None),patch.object(prepare,'download_archive',return_value=('source.tar.gz::https://example.com/source','c'*64)) as archive,patch.object(prepare,'notes',return_value='Upstream notes'),patch.object(prepare,'output'):
            prepare.main()
            recipe=(pathlib.Path(folder)/'PKGBUILD').read_text()
            state=json.loads((pathlib.Path(folder)/'upstream.json').read_text())
            self.assertEqual(state['fonts_commit'],fonts)
            self.assertEqual(state['app_id'],'ai.storyteller.figcraft')
            self.assertTrue(state['cli']);self.assertTrue(state['mime'])
            self.assertEqual(archive.call_args_list[1].args[:2],('storytold/craft-fonts',fonts))
            for required in ['-p figcraft -p figcraft-cli','FIGCRAFT_BUILD_SHA','usr/bin/figcraft-cli','desktop-file-validate','share/mime/packages','share/metainfo','assets/app-icon/hicolor']:
                self.assertIn(required,recipe)
            self.assertNotIn('alsa-lib',recipe)
            import subprocess
            subprocess.run(['bash','-n',str(pathlib.Path(folder)/'PKGBUILD')],check=True)

class SolidCraftTests(unittest.TestCase):
    def test_recipe_uses_upstream_identity_and_layout(self):
        sha='a'*40
        def api(path):
            if path=='repos/tangency-labs/solidcraft':return {'default_branch':'main'}
            if path=='repos/tangency-labs/solidcraft/commits/main':return {'sha':sha,'commit':{'committer':{'date':'2026-10-31T00:00:00Z'}}}
            raise AssertionError(path)
        def content(repo,path,commit):
            self.assertEqual(repo,'tangency-labs/solidcraft')
            if path=='Cargo.toml':return '[workspace.package]\nversion="0.28.0"\n'
            if path=='packaging/env.sh':return 'APP_ID=io.tangencylabs.solidcraft\n'
            if path=='packaging/linux/package.sh':return 'cargo build --release --locked -p solidcraft -p solidcraft-cli'
            raise AssertionError(path)
        with tempfile.TemporaryDirectory() as folder,patch('sys.argv',['prepare.py','solidcraft','--directory',folder]),patch.object(prepare,'api',api),patch.object(prepare,'content',content),patch.object(prepare,'previous',return_value=None),patch.object(prepare,'download_archive',return_value=('source.tar.gz::https://example.com/source','c'*64)) as archive,patch.object(prepare,'notes',return_value='Upstream notes'),patch.object(prepare,'output'):
            prepare.main()
            recipe=(pathlib.Path(folder)/'PKGBUILD').read_text()
            state=json.loads((pathlib.Path(folder)/'upstream.json').read_text())
            self.assertEqual(state['app_id'],'io.tangencylabs.solidcraft')
            self.assertEqual(archive.call_count,1)
            for value in ['-p solidcraft -p solidcraft-cli','assets/platforms/linux/','assets/icons/app/linux/exports/hicolor','release/solvecraft-cli','THIRD-PARTY-LICENSES.txt']:
                self.assertIn(value,recipe)
            self.assertNotIn('ai.storyteller.solidcraft',recipe)
            import subprocess,re
            self.assertFalse(set(re.findall(r'@[A-Z_]+@',recipe))-{'@VERSION@','@DATE@'})
            subprocess.run(['bash','-n',str(pathlib.Path(folder)/'PKGBUILD')],check=True)

    def test_unapproved_community_repository_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=pathlib.Path(folder)/'apps.json'
            path.write_text(json.dumps({'solidcraft':{'repo':'other/solidcraft','kind':'solidcraft','description':'CAD'}}))
            with self.assertRaises(ValueError):registry.load_apps(path)
