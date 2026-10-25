"""Build a self-contained Python payload from the project's installed runtime.

No candidate data, credentials, output, git checkout or browser state is copied.
Rebuild with the same locked environment to reproduce a local installer.
"""
import base64
import io
import json
import re
import shutil
import sys
from importlib import metadata
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
PAYLOAD = ROOT / 'desktop' / 'payload'


def copy_tree(source, target):
    shutil.copytree(source, target, dirs_exist_ok=True,
        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'site-packages'))


def main():
    PAYLOAD.mkdir(parents=True, exist_ok=True)
    runtime = PAYLOAD / 'runtime'
    runtime.mkdir(exist_ok=True)
    base = Path(sys.base_prefix)
    for name in ('python.exe', 'pythonw.exe', 'python3.dll', f'python{sys.version_info.major}{sys.version_info.minor}.dll',
                 'vcruntime140.dll', 'vcruntime140_1.dll', 'LICENSE.txt'):
        source = base / name
        if source.exists():shutil.copy2(source, runtime / name)
    copy_tree(base / 'Lib', runtime / 'Lib')
    copy_tree(base / 'DLLs', runtime / 'DLLs')
    packages = Path(sys.prefix) / 'Lib' / 'site-packages'
    # Replaced optional packages must not leave old version metadata in the bundle.
    bundled = runtime / 'Lib' / 'site-packages'
    for pattern in ('python_jobspy-*.dist-info', 'markdownify-*.dist-info'):
        for old in bundled.glob(pattern):
            old.resolve().relative_to(bundled.resolve())
            shutil.rmtree(old)
    shutil.copytree(packages, runtime / 'Lib' / 'site-packages', dirs_exist_ok=True,
        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'pip', 'pip-*.dist-info'))
    # Explicit allowlist, never copy the project root recursively.
    for name in ('app', 'static', 'docs'):
        copy_tree(ROOT / name, PAYLOAD / name)
    # Incremental bundles must not retain catalogs removed from the source tree.
    locale_dir = PAYLOAD / 'static' / 'locales'
    for catalog in locale_dir.glob('*.json'):
        if not (ROOT / 'static' / 'locales' / catalog.name).exists():
            catalog.unlink()
    shutil.copy2(ROOT / 'profile.example.json', PAYLOAD / 'profile.example.json')
    for name in ('LICENSE', 'README.md'):
        if (ROOT / name).exists():shutil.copy2(ROOT / name, PAYLOAD / name)
    inventory = [{'name': d.metadata['Name'], 'version': d.version,
                  'license': d.metadata.get('License-Expression') or d.metadata.get('License', ''),
                  'homepage': d.metadata.get('Home-page', '')} for d in metadata.distributions()]
    (PAYLOAD / 'runtime-packages.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')
    # Reuse the actual app avatar, including the same crop as favicon.svg.
    svg = (ROOT / 'static' / 'favicon.svg').read_text(encoding='utf-8')
    data = re.search(r'data:image/png;base64,([^"\s]+)', svg).group(1)
    avatar = Image.open(io.BytesIO(base64.b64decode(data))).convert('RGBA')
    crop = avatar.crop((400, 210, 790, 600)).resize((240, 240), Image.Resampling.LANCZOS)
    icon = Image.new('RGBA', (256, 256), '#e7f5f4')
    icon.alpha_composite(crop, (8, 8))
    mask = Image.new('L', (256, 256));ImageDraw.Draw(mask).rounded_rectangle((0, 0, 255, 255), radius=62, fill=255)
    icon.putalpha(mask)
    assets = ROOT / 'desktop' / 'assets';assets.mkdir(exist_ok=True)
    icon.save(assets / 'icon.png')
    icon.save(assets / 'icon.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
    print('Prepared standalone runtime, application assets and dependency inventory; no personal data included.')


if __name__ == '__main__':main()
