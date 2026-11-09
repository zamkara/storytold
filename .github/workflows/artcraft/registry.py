"""Validate the supported application registry and emit the CI matrix."""
import json,pathlib,re
HERE=pathlib.Path(__file__).resolve().parent
# Community apps live outside the storytold organisation; the tuple is (repository, builder).
COMMUNITY_APPS={
    'solidcraft':('tangency-labs/solidcraft','solidcraft'),
    'fieldcraft':('tangency-labs/fieldcraft','fieldcraft'),
    'pcbcraft':('tangency-labs/pcbcraft','craft'),
}
BUILDERS=('craft','tauri','solidcraft','fieldcraft')

def load_apps(path=None,include_pending=False):
    apps=json.loads((path or HERE/'apps.json').read_text())
    if not isinstance(apps,dict) or not apps:raise ValueError('Application registry must be a nonempty object')
    active={}
    for name,app in apps.items():
        if name=='artcraft' or not re.fullmatch(r'[a-z0-9][a-z0-9-]*',name):raise ValueError('Invalid or reserved package name: '+name)
        repo=app.get('repo','');kind=app.get('kind','craft');community=COMMUNITY_APPS.get(name)
        official=re.fullmatch(r'storytold/[A-Za-z0-9_.-]+',repo)
        if not (official or (community and repo==community[0] and kind==community[1])):raise ValueError('Invalid upstream repository: '+name)
        if not app.get('description'):raise ValueError('Missing description: '+name)
        if kind not in BUILDERS:raise ValueError('Unknown builder: '+name)
        if kind=='tauri' and not app.get('crate_path'):raise ValueError('Missing Tauri crate path: '+name)
        if not include_pending and app.get('pending'):continue
        active[name]=app
    if not active:raise ValueError('Application registry must contain an active application')
    return active

if __name__=='__main__':print('apps='+json.dumps(list(load_apps()),separators=(',',':')))
