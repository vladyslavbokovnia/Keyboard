from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

base = Path('/home/ubuntu/upload/Gboard+-+the+Google+Keyboard_18.3.1.977415014-release-arm64-v8a_APKPure.apk')
out = Path('/home/ubuntu/gboard_patch/Gboard_transparent_unsigned.apk')
patched = Path('/home/ubuntu/gboard_patch/patched_theme')
changed = {p.name: p for p in patched.glob('*.binarypb') if p.read_bytes() != (Path('/home/ubuntu/gboard_patch/orig/assets/theme') / p.name).read_bytes()}
with ZipFile(base, 'r') as zin, ZipFile(out, 'w', ZIP_DEFLATED, compresslevel=6) as zout:
    for info in zin.infolist():
        if info.filename.startswith('META-INF/'):
            continue
        if info.filename.startswith('assets/theme/') and info.filename.rsplit('/', 1)[-1] in changed:
            data = changed[info.filename.rsplit('/', 1)[-1]].read_bytes()
        else:
            data = zin.read(info.filename)
        zout.writestr(info, data)
print(f'replaced {len(changed)} theme files')
