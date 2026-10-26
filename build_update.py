"""Build the three-file update accepted by the original stable launcher."""
import ast,hashlib,json,zipfile
from pathlib import Path

def build(root=Path(__file__).resolve().parent, destination=None):
    tree=ast.parse((root/'seal_app.py').read_text(encoding='utf-8'))
    version=next(n.value.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='VERSION' for t in n.targets))
    files={name:(root/name).read_bytes() for name in ('seal_app.py','vision_tracker.py')}
    for name,data in files.items():compile(data,name,'exec')
    manifest={'product':'SealVision','version':version,'launcher_min':1,'sha256':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()}}
    destination=destination or root/'dist';destination.mkdir(parents=True,exist_ok=True)
    archive=destination/f'SealVision-update-{version}.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
        z.writestr('version.json',json.dumps(manifest,indent=2))
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist())==set(files)|{'version.json'}
        for name,digest in manifest['sha256'].items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
    print(archive);print('SHA256',hashlib.sha256(archive.read_bytes()).hexdigest())
    return archive

if __name__=='__main__':build()
