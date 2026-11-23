"""生成 packaging/metatest.ico（无 Pillow 时跳过，不影响打包）。"""

from __future__ import annotations

from pathlib import Path


def build_icon(out: Path) -> bool:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return False

    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 8, size - 8, size - 8], radius=56, fill=(31, 111, 235, 255))

    # 白色 M 折线（与侧栏 logo 一致）
    pts = [(70, 178), (70, 78), (128, 140), (186, 78), (186, 178)]
    d.line(pts, fill=(255, 255, 255, 255), width=22, joint="curve")
    for p in (pts[0], pts[-1]):
        d.ellipse([p[0] - 11, p[1] - 11, p[0] + 11, p[1] + 11], fill=(255, 255, 255, 255))

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return True


if __name__ == "__main__":
    target = Path(__file__).resolve().parent.parent / "packaging" / "metatest.ico"
    print("icon written" if build_icon(target) else "Pillow not installed, skipped")
