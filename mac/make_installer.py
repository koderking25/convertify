"""Build the installer that puts the plugins where DAWs actually look.

A zip in your Downloads folder is not an installed plugin: somebody still has to know that an
Audio Unit goes in one folder and a VST3 in another, and that neither of them is the one the
browser picked. This builds the thing that does it for you.

    python3 mac/make_installer.py

It installs into /Library/Audio/Plug-Ins, which every DAW scans and which is where every other
plugin maker puts theirs. That folder belongs to the whole Mac, so the installer asks for a
password once, the same as any other plugin installer.
"""
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILT = ROOT / "plugin" / "build" / "ConvertifyPlugin_artefacts" / "Release"
OUT = ROOT / "mac" / "build"
IDENTIFIER = "tech.midify.convertify.plugins"


def version_of(bundle):
    info = plistlib.loads((bundle / "Contents" / "Info.plist").read_bytes())
    return info.get("CFBundleShortVersionString", "0")


def main():
    au, vst3 = BUILT / "AU" / "Convertify.component", BUILT / "VST3" / "Convertify.vst3"
    for b in (au, vst3):
        if not b.exists():
            sys.exit(f"missing {b.name}. Build the plugin first:\n"
                     f"  cmake --build plugin/build --config Release")

    version = version_of(au)
    if version_of(vst3) != version:
        sys.exit("the two plugins are different versions; build them both again")

    staging = OUT / "pkg-root"
    shutil.rmtree(staging, ignore_errors=True)
    components = staging / "Components"
    vst3dir = staging / "VST3"
    components.mkdir(parents=True)
    vst3dir.mkdir(parents=True)
    # ditto rather than copytree: it keeps the bundle's signature and symlinks intact.
    subprocess.run(["ditto", str(au), str(components / au.name)], check=True)
    subprocess.run(["ditto", str(vst3), str(vst3dir / vst3.name)], check=True)

    scripts = OUT / "pkg-scripts"
    shutil.rmtree(scripts, ignore_errors=True)
    scripts.mkdir(parents=True)
    # macOS keeps a cache of Audio Units. Without clearing it, a DAW can keep showing the old
    # one, or not see a new one at all, and it looks like the installer did nothing.
    after = scripts / "postinstall"
    after.write_text(
        "#!/bin/bash\n"
        "killall -9 AudioComponentRegistrar 2>/dev/null\n"
        "exit 0\n")
    after.chmod(0o755)

    OUT.mkdir(parents=True, exist_ok=True)
    inner = OUT / "plugins-payload.pkg"
    subprocess.run([
        "pkgbuild",
        "--root", str(staging),
        "--scripts", str(scripts),
        "--identifier", IDENTIFIER,
        "--version", version,
        "--install-location", "/Library/Audio/Plug-Ins",
        str(inner)], check=True, capture_output=True)

    welcome = OUT / "welcome.html"
    welcome.write_text(f"""<html><body style="font: 14px -apple-system; color: #112015">
<h2 style="margin:0 0 10px">Convertify {version}, as a plugin 🎧</h2>
<p>This puts two files where your DAWs look for them:</p>
<ul>
  <li><b>Convertify.component</b> into Components, which is the Audio Unit.
      That is the one Logic and GarageBand use.</li>
  <li><b>Convertify.vst3</b> into VST3, which is what everything else uses.</li>
</ul>
<p>Restart your DAW afterwards. They only look for new plugins when they start, so one that
was already open will swear blind that nothing happened.</p>
<p><b>Convertify itself has to be installed too.</b> The plugin is the window; the app does
the work. If it is not running when you open the plugin, the plugin goes and starts it.</p>
</body></html>""")

    distribution = OUT / "distribution.xml"
    distribution.write_text(f"""<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>Convertify plugins</title>
    <welcome file="welcome.html" mime-type="text/html"/>
    <options customize="never" require-scripts="false" hostArchitectures="arm64,x86_64"/>
    <pkg-ref id="{IDENTIFIER}"/>
    <choices-outline><line choice="default"/></choices-outline>
    <choice id="default" title="Convertify plugins"><pkg-ref id="{IDENTIFIER}"/></choice>
    <pkg-ref id="{IDENTIFIER}" version="{version}">plugins-payload.pkg</pkg-ref>
</installer-gui-script>""")

    final = OUT / "Convertify-plugins.pkg"
    subprocess.run([
        "productbuild",
        "--distribution", str(distribution),
        "--package-path", str(OUT),
        "--resources", str(OUT),
        str(final)], check=True, capture_output=True)

    inner.unlink(missing_ok=True)
    shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(scripts, ignore_errors=True)

    # Say what is really in it, rather than trusting that it worked.
    listing = subprocess.run(["pkgutil", "--payload-files", str(final)],
                             capture_output=True, text=True).stdout
    tops = sorted({line.strip("./").split("/")[0] for line in listing.splitlines()
                   if line.strip("./")})
    print(f"built {final}  ({final.stat().st_size / 1e6:.1f} MB), version {version}")
    print(f"  it installs into /Library/Audio/Plug-Ins: {', '.join(tops)}")
    for wanted in ("Components", "VST3"):
        if wanted not in tops:
            sys.exit(f"  but {wanted} is not in the payload, so this would install nothing useful")
    return 0


if __name__ == "__main__":
    sys.exit(main())
