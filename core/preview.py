"""PIL preview of a theme (gallery thumbnails, editor background)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

from .model import H, T_BAR, T_DATETIME, T_IMAGE, T_TEXT, T_VALUE, W
from .smartmonitor.render import load_font, points_to_pixels
from .smartmonitor.ui import SmartMonitorThemeBundle, resolve_theme_path


_FRAME_CACHE: dict = {}


def _frames(base_dir, raw_path: str) -> list:
    """All frames of an (animated) image path ./images/x_00.png → [x_00, x_01, …]."""
    key = (str(base_dir), raw_path)
    if key in _FRAME_CACHE:
        return _FRAME_CACHE[key]
    p = resolve_theme_path(base_dir, raw_path)
    stem = p.stem
    digits = len(stem) - len(stem.rstrip("0123456789"))
    if digits:
        prefix = stem[:-digits]
        files, i = [], 0
        while (p.parent / f"{prefix}{i:0{digits}d}{p.suffix}").is_file():
            files.append(p.parent / f"{prefix}{i:0{digits}d}{p.suffix}")
            i += 1
        files = files or ([p] if p.is_file() else [])
    else:
        files = [p] if p.is_file() else []
    _FRAME_CACHE[key] = files
    return files


_IMG_CACHE: dict = {}


def _open(path, mode, size):
    key = (str(path), mode, size)
    im = _IMG_CACHE.get(key)
    if im is None:
        im = Image.open(path).convert(mode)
        if size and im.size != size:
            im = im.resize(size)
        if len(_IMG_CACHE) > 200:
            _IMG_CACHE.clear()
        _IMG_CACHE[key] = im
    return im


def background_image(bundle: SmartMonitorThemeBundle, frame: int = 0) -> Image.Image:
    parent = bundle.theme.widget_parents[0] if bundle.theme.widget_parents else None
    if parent and parent.background_image_path:
        try:
            files = _frames(bundle.base_dir, parent.background_image_path)
            if files:
                return _open(files[frame % len(files)], "RGB", (W, H)).copy()
        except Exception:
            pass
    color = (parent.background_color & 0xFFFFFF) if parent else 0
    return Image.new("RGB", (W, H), f"#{color:06x}")


def _fmt_datetime(fmt: str, now: datetime) -> str:
    out = fmt.strip()
    for key, val in (("yyyy", f"{now.year:04d}"), ("mm", f"{now.month:02d}"), ("dd", f"{now.day:02d}"),
                     ("hh", f"{now.hour:02d}"), ("nn", f"{now.minute:02d}"), ("ss", f"{now.second:02d}")):
        out = out.replace(key, val)
    return out


def render(bundle: SmartMonitorThemeBundle, values: dict[int, int] | None = None,
           draw_widgets: bool = True, t_ms: int = 0) -> Image.Image:
    """t_ms : temps écoulé, pour choisir l'image courante des animations."""
    parent = bundle.theme.widget_parents[0] if bundle.theme.widget_parents else None
    delay = max(20, int(getattr(parent, "image_delay", 100) or 100)) if parent else 100
    img = background_image(bundle, t_ms // delay)
    if not draw_widgets:
        return img
    draw = ImageDraw.Draw(img, "RGBA")
    now = datetime.now()
    for w in bundle.theme.widgets:
        g = w.geometry
        try:
            if w.widget_type == T_IMAGE:
                files = _frames(bundle.base_dir, str(w.raw_fields.get("imagePath", "")))
                if files:
                    d_ms = max(20, int(w.raw_fields.get("imageDelay", "100") or 100))
                    im = _open(files[(t_ms // d_ms) % len(files)], "RGBA", (max(1, g.width), max(1, g.height)))
                    img.paste(im, (g.x, g.y), im)
            elif w.widget_type == T_BAR:
                st = w.style
                pct = 50
                if values and w.sensor:
                    pct = max(0, min(100, values.get(w.sensor.fast_sensor, 50)))
                bg = f"#{(st.bg_color if st else 0x303030) & 0xFFFFFF:06x}"
                fg = f"#{(st.fg_color if st else 0x00c8ff) & 0xFFFFFF:06x}"
                fr = f"#{(st.frame_color if st else 0x606060) & 0xFFFFFF:06x}"
                draw.rectangle([g.x, g.y, g.x + g.width - 1, g.y + g.height - 1], fill=bg, outline=fr)
                draw.rectangle([g.x + 1, g.y + 1, g.x + 1 + int((g.width - 3) * pct / 100), g.y + g.height - 2],
                               fill=fg)
            elif w.font is not None:
                if w.widget_type == T_VALUE:
                    text = w.font.text or "42"
                    if values and w.sensor and w.sensor.fast_sensor in values:
                        text = str(values[w.sensor.fast_sensor])
                elif w.widget_type == T_DATETIME:
                    text = _fmt_datetime(w.datetime_format or "hh:nn:ss", now)
                else:
                    text = w.font.text
                font = load_font(w.font, pixel_size=points_to_pixels(w.font.size))
                color = f"#{w.font.color & 0xFFFFFF:06x}"
                align = int(w.raw_fields.get("hAlign", 0) or 0)
                tw = draw.textlength(text, font=font)
                x = g.x
                if w.widget_type != T_TEXT:
                    if align == 1:
                        x = g.x + (g.width - tw) / 2
                    elif align == 2:
                        x = g.x + g.width - tw
                draw.text((x, g.y), text, font=font, fill=color)
        except Exception:
            continue
    return img


def thumbnail(ui_path: str | Path, size: tuple[int, int] = (240, 160)) -> Image.Image:
    from .smartmonitor.ui import parse_theme_bundle
    try:
        img = render(parse_theme_bundle(ui_path))
    except Exception:
        img = Image.new("RGB", (W, H), "#202020")
    return img.resize(size, Image.Resampling.LANCZOS)
