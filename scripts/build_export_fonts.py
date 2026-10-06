"""Cut the static fonts the brief PDF embeds from the site's variable fonts.

The PDF is set in the same Inter and JetBrains Mono as the web page. The
page ships each as one variable WOFF2 file; fpdf2 embeds one static TrueType
file per weight. This script makes those files from the page's own, so the
two never drift, and copies the licence texts beside them.

    python scripts/build_export_fonts.py ../alkira-account-list/web/app/fonts

Needs fonttools and brotli (requirements-dev.txt). The output is committed
under assets/fonts/, so this only runs again when the site changes its fonts.
"""

import shutil
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

import pdf_fonts

OUTPUT_DIR = pdf_fonts.FONT_DIR
LICENCES: tuple[str, ...] = ("Inter-LICENSE.txt", "JetBrainsMono-LICENSE.txt")
# Tables that only serve a variable font or on-screen hinting. A PDF needs neither.
UNUSED_TABLES: tuple[str, ...] = ("STAT", "avar", "HVAR", "MVAR", "gasp", "prep", "fpgm", "cvt ")
# Name table records: family, style, full name, PostScript name.
FAMILY_ID, STYLE_ID, FULL_NAME_ID, POSTSCRIPT_ID = 1, 2, 4, 6


def _axes(font: TTFont, face: pdf_fonts.Face) -> dict[str, float]:
    """Where on each of the font's axes this face sits."""
    wanted = {"wght": float(face.weight), "opsz": face.optical_size}
    return {axis.axisTag: wanted[axis.axisTag] for axis in font["fvar"].axes}


def _rename(font: TTFont, face: pdf_fonts.Face) -> None:
    """Name the face for what it is, so a PDF viewer lists it by weight."""
    family, style = face.file.removesuffix(".ttf").split("-")
    names = {
        FAMILY_ID: family, STYLE_ID: style,
        FULL_NAME_ID: f"{family} {style}", POSTSCRIPT_ID: f"{family}-{style}",
    }
    table = font["name"]
    for record in list(table.names):
        if record.nameID in names:
            table.setName(names[record.nameID], record.nameID, record.platformID, record.platEncID, record.langID)


def build_face(source_dir: Path, face: pdf_fonts.Face) -> Path:
    """One static TrueType file cut from the variable font, written to assets/fonts/."""
    font = TTFont(source_dir / face.source)
    instancer.instantiateVariableFont(font, _axes(font, face), inplace=True)
    font.flavor = None  # plain TrueType, not WOFF2
    for tag in UNUSED_TABLES:
        if tag in font:
            del font[tag]
    font["OS/2"].usWeightClass = face.weight
    _rename(font, face)
    target = OUTPUT_DIR / face.file
    font.save(target)
    return target


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write(f"usage: {argv[0]} <folder holding the site's .woff2 fonts>\n")
        return 2
    source_dir = Path(argv[1])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for face in pdf_fonts.FACES:
        target = build_face(source_dir, face)
        sys.stdout.write(f"{target.name}  {target.stat().st_size:,} bytes\n")
    for licence in LICENCES:
        shutil.copyfile(source_dir / licence, OUTPUT_DIR / licence)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
