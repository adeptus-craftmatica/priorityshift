# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

ROOT = Path(SPECPATH)

block_cipher = None


# Walk the source tree to build hidden imports for every app/ module. More
# reliable than collect_submodules(), which needs the package importable on
# the build machine — and matches the same approach used for this app's
# sibling project (StreamShift) since PyInstaller's static analysis can miss
# imports made inside function bodies (e.g. blueprint registration).
def _find_modules(root: Path) -> list[str]:
    modules = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != '__pycache__' and not d.startswith('.')]
        for fname in filenames:
            if fname.endswith('.py'):
                rel = Path(dirpath).relative_to(root.parent)
                mod = str(rel / fname[:-3]).replace(os.sep, '.').replace('/', '.')
                modules.append(mod)
    return modules


_app_modules = _find_modules(ROOT / 'app')

_icon_icns = ROOT / 'app' / 'static' / 'icon.icns'
_icon_ico = ROOT / 'app' / 'static' / 'icon.ico'

a = Analysis(
    [str(ROOT / 'main.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Jinja templates and static assets — loaded by Flask at runtime via
        # its template/static folder mechanism, not via Python import, so
        # they have to be bundled as data rather than relying on Analysis.
        (str(ROOT / 'app' / 'templates'), 'app/templates'),
        (str(ROOT / 'app' / 'static'), 'app/static'),
        # Alembic migration scripts — loaded by file path at runtime, same
        # reasoning as templates/static above.
        (str(ROOT / 'migrations'), 'migrations'),
    ],
    hiddenimports=[
        *_app_modules,
        'seed',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'flask',
        'flask.cli',
        'flask_sqlalchemy',
        'flask_migrate',
        'flask_login',
        'flask_wtf',
        'flask_wtf.csrf',
        'wtforms',
        'email_validator',
        'werkzeug',
        'werkzeug.serving',
        'jinja2',
        'sqlalchemy',
        'sqlalchemy.sql.default_comparator',
        'alembic',
        'reportlab',
        'reportlab.graphics.barcode',
        'openpyxl',
        'pyotp',
        'authlib',
        'authlib.integrations.flask_client',
        'authlib.integrations.requests_client',
        'authlib.jose',
        'joserfc',
        'cryptography',
        'cryptography.hazmat.primitives.ciphers.aead',
        'cryptography.exceptions',
        'requests',
        'dotenv',
        'sqlite3',
        '_sqlite3',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PriorityShift',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(_icon_icns) if sys.platform == 'darwin' and _icon_icns.exists()
        else str(_icon_ico) if sys.platform == 'win32' and _icon_ico.exists()
        else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PriorityShift',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='PriorityShift.app',
        icon=str(_icon_icns) if _icon_icns.exists() else None,
        bundle_identifier='com.priorityshift.app',
        info_plist={
            'CFBundleName': 'PriorityShift',
            'CFBundleDisplayName': 'PriorityShift',
            'CFBundleShortVersionString': '1.1.0',
            'CFBundleVersion': '1.1.0',
            'NSHighResolutionCapable': True,
        },
    )
