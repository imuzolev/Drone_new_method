#!/usr/bin/env python3
"""Replace barcode models in warehouse_phase0.sdf with QR-textured versions.

Textures are referenced from the WSL home directory because Gazebo Harmonic /
Ogre2 is more reliable with ext4 paths than with `/mnt/c/...`.
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SDF_PATH = PROJECT_ROOT / "simulation" / "worlds" / "warehouse_phase0.sdf"
TEXTURE_DIR = "/home/imuzolev/gz_barcodes"


def make_textured_model(name: str, pose: str, texture_file: str) -> str:
    texture_path = f"{TEXTURE_DIR}/{texture_file}"
    return (
        f'    <model name="{name}"><static>true</static><pose>{pose}</pose>\n'
        f'      <link name="l">\n'
        f'        <visual name="v">\n'
        f'          <geometry><box><size>0.12 0.005 0.07</size></box></geometry>\n'
        f'          <material>\n'
        f'            <ambient>1 1 1 1</ambient>\n'
        f'            <diffuse>1 1 1 1</diffuse>\n'
        f'            <pbr>\n'
        f'              <metal>\n'
        f'                <albedo_map>{texture_path}</albedo_map>\n'
        f'                <metalness>0.0</metalness>\n'
        f'                <roughness>1.0</roughness>\n'
        f'              </metal>\n'
        f'            </pbr>\n'
        f'          </material>\n'
        f'        </visual>\n'
        f'      </link>\n'
        f'    </model>'
    )


TEXTURED_PATTERN = re.compile(
    r'<model name="(bc[LR]_\d+_\d)">\s*<static>true</static>'
    r'\s*<pose>([^<]+)</pose>'
    r'\s*<link name="l">'
    r'\s*<visual name="v">'
    r'\s*<geometry><box><size>0\.12 0\.005 0\.07</size></box></geometry>'
    r'\s*<material>'
    r'.*?'
    r'</material>'
    r'\s*</visual>'
    r'\s*</link>'
    r'\s*</model>',
    re.DOTALL,
)


def main() -> None:
    sdf = SDF_PATH.read_text(encoding="utf-8")

    replacements = 0

    def replacer(m: re.Match) -> str:
        nonlocal replacements
        model_name = m.group(1)
        pose = m.group(2).strip()

        side = "L" if model_name.startswith("bcL") else "R"
        parts = model_name.split("_")
        section = int(parts[1])
        level = int(parts[2])

        texture_file = f"barcode_{side}_{section:02d}_{level}.png"
        replacements += 1
        return make_textured_model(model_name, pose, texture_file)

    new_sdf = TEXTURED_PATTERN.sub(replacer, sdf)

    SDF_PATH.write_text(new_sdf, encoding="utf-8")
    print(f"Replaced {replacements} barcode models in {SDF_PATH}")


if __name__ == "__main__":
    main()
