"""Helpers to create / edit SmartMonitor themes (vendor .ui format) from code."""
from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image

from .sensors import AIDA_TYPE
from .smartmonitor.ui import (
    FontSpec,
    Geometry,
    SensorSpec,
    SmartMonitorTheme,
    SmartMonitorThemeBundle,
    StyleSpec,
    Widget,
    WidgetParent,
    parse_theme_bundle,
    write_theme_file,
)

W, H = 480, 320

T_TEXT, T_BAR, T_IMAGE, T_VALUE, T_DATETIME = 2, 3, 4, 5, 6
TYPE_NAMES = {T_TEXT: "StaticText", T_BAR: "ProgressBar", T_IMAGE: "Image",
              T_VALUE: "Number", T_DATETIME: "DateTime"}
TYPE_LABELS = {T_TEXT: "Texte", T_BAR: "Barre", T_IMAGE: "Image", T_VALUE: "Valeur capteur",
               T_DATETIME: "Date / heure"}

_TEXT_RAW = {"isHide": "0", "characterSet": "0", "isTransparent": "1", "isAutoLineBreak": "0",
             "backgroundColor": "ffffffff", "hAlign": "0", "vAlign": "0", "isEnable": "1"}


def argb(hex_rgb: str, alpha: int = 0xFF) -> tuple[str, int]:
    """'#RRGGBB' -> ('ffrrggbb', int)."""
    h = hex_rgb.lstrip("#")[-6:].lower()
    raw = f"{alpha:02x}{h}"
    return raw, int(raw, 16)


def rgb_hex(value: int) -> str:
    return f"#{value & 0xFFFFFF:06x}"


def make_font(text: str, size: int = 16, color: str = "#ffffff", name: str = "Arial",
              bold: bool = True, italic: bool = False) -> FontSpec:
    raw, val = argb(color)
    return FontSpec(text=text, name=name, color_raw=raw, color=val, size=size,
                    bold_value=int(bold), italic_value=int(italic), bold=bold, italic=italic)


def new_widget(kind: int, x: int, y: int, w: int, h: int, **kw) -> Widget:
    wid = Widget(widget_type=kind, parent_name="background", geometry=Geometry(x, y, w, h))
    if kind == T_TEXT:
        wid.font = make_font(kw.get("text", "Texte"), kw.get("size", 14), kw.get("color", "#ffffff"),
                             kw.get("font", "Arial"), kw.get("bold", True))
        wid.raw_fields = dict(_TEXT_RAW, hAlign=str(kw.get("align", 0)))
    elif kind == T_VALUE:
        wid.font = make_font(kw.get("sample", "42"), kw.get("size", 18), kw.get("color", "#ffffff"),
                             kw.get("font", "Arial"), kw.get("bold", True))
        wid.raw_fields = dict(_TEXT_RAW, isAutoLineBreak="1", hAlign=str(kw.get("align", 1)))
        wid.sensor = SensorSpec(fast_sensor=0, sensor_type_name=AIDA_TYPE, sensor_name=AIDA_TYPE,
                                reading_name=kw.get("sensor", "SCPUUTI"), is_div_1204=False)
    elif kind == T_DATETIME:
        fmt = kw.get("format", "hh:nn:ss")
        sample = "12:00:00" if "h" in fmt else ("01-01-2026" if fmt.startswith("dd") else "2026-01-01")
        wid.font = make_font(sample, kw.get("size", 18), kw.get("color", "#ffffff"),
                             kw.get("font", "Arial"), kw.get("bold", True))
        wid.datetime_format = fmt
        braw, _ = argb("#000000")
        wid.raw_fields = {"isEnable": "1", "isHide": "0", "fontColor": wid.font.color_raw,
                          "backgroundColor": braw, "isTransparent": "1",
                          "hAlign": str(kw.get("align", 1)), "vAlign": "1"}
    elif kind == T_BAR:
        bg_raw, bg = argb(kw.get("bg", "#303030"))
        fg_raw, fg = argb(kw.get("fg", "#00c8ff"))
        fr_raw, fr = argb(kw.get("frame", "#606060"))
        wid.style = StyleSpec(show_type=0, bg_color_raw=bg_raw, bg_color=bg, fg_color_raw=fg_raw,
                              fg_color=fg, frame_color_raw=fr_raw, frame_color=fr)
        wid.sensor = SensorSpec(fast_sensor=0, sensor_type_name=AIDA_TYPE, sensor_name=AIDA_TYPE,
                                reading_name=kw.get("sensor", "SCPUUTI"), is_div_1204=False)
        wid.raw_fields = {"isHide": "0", "isEnable": "1"}
    elif kind == T_IMAGE:
        wid.raw_fields = {"imagePath": kw.get("path", ""), "imageDelay": "0", "isHide": "0", "isEnable": "1"}
    return wid


def new_theme(theme_dir: str | Path, name: str, background: str | Path | None = None,
              color: str = "#000000") -> SmartMonitorThemeBundle:
    theme_dir = Path(theme_dir)
    (theme_dir / "images").mkdir(parents=True, exist_ok=True)
    bg_rel = set_background(theme_dir, background, color)
    raw, val = argb("#ffffff")
    parent = WidgetParent(object_name="background", widget_type=1, geometry=Geometry(10, 10, W, H),
                          background_type=1, background_color_raw=raw, background_color=val,
                          background_image_path=bg_rel, image_delay=1)
    theme = SmartMonitorTheme(path=str(theme_dir / f"{name}.ui"), widget_parents=[parent], widgets=[])
    return SmartMonitorThemeBundle(ui_path=theme.path, base_dir=str(theme_dir), theme=theme)


def fit_cover(img: Image.Image, w: int = W, h: int = H) -> Image.Image:
    """Resize + center-crop to exactly w x h."""
    img = img.convert("RGB")
    scale = max(w / img.width, h / img.height)
    img = img.resize((max(w, round(img.width * scale)), max(h, round(img.height * scale))),
                     Image.Resampling.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def set_background(theme_dir: str | Path, source: str | Path | Image.Image | None,
                   color: str = "#000000") -> str:
    """Write images/background.jpg (480x320) and return its relative path."""
    theme_dir = Path(theme_dir)
    (theme_dir / "images").mkdir(parents=True, exist_ok=True)
    if source is None:
        img = Image.new("RGB", (W, H), color)
    elif isinstance(source, Image.Image):
        img = fit_cover(source)
    else:
        img = fit_cover(Image.open(source))
    # unique file name so a re-upload is never served from cache
    _clear_backgrounds(theme_dir)
    import time
    name = f"background_{int(time.time())}.jpg"
    img.save(theme_dir / "images" / name, quality=95)
    return f"./images/{name}"


MAX_FRAMES = 12  # the vendor themes never exceed 12 frames (~3.7 MB on the screen)


def _clear_backgrounds(theme_dir: Path):
    for old in list((theme_dir / "images").glob("background*.jpg")) + list((theme_dir / "images").glob("bg_*.jpg")):
        try:
            old.unlink()
        except OSError:
            pass


def set_background_frames(theme_dir: str | Path, frames: list[Image.Image]) -> str:
    """Animated background: images/bg_<stamp>_00.jpg ... (max 12 frames). Returns path of frame 0."""
    import time
    theme_dir = Path(theme_dir)
    (theme_dir / "images").mkdir(parents=True, exist_ok=True)
    _clear_backgrounds(theme_dir)
    frames = sample_frames(frames, MAX_FRAMES)
    stamp = int(time.time())
    for i, fr in enumerate(frames):
        fit_cover(fr).save(theme_dir / "images" / f"bg_{stamp}_{i:02d}.jpg", quality=92)
    return f"./images/bg_{stamp}_00.jpg"


def sample_frames(frames: list, n: int) -> list:
    if len(frames) <= n:
        return list(frames)
    step = len(frames) / n
    return [frames[int(i * step)] for i in range(n)]


def read_gif(path: str | Path) -> tuple[list[Image.Image], int]:
    """Return (frames RGBA, delay ms) of an animated GIF/WebP/APNG."""
    from PIL import ImageSequence
    with Image.open(path) as im:
        frames, delays = [], []
        for fr in ImageSequence.Iterator(im):
            frames.append(fr.convert("RGBA"))
            delays.append(int(fr.info.get("duration", 100) or 100))
    keep = sample_frames(list(range(len(frames))), MAX_FRAMES)
    # stretch the delay when frames are dropped so the speed stays similar
    total = sum(delays)
    delay = max(50, min(2000, int(total / max(1, len(keep)))))
    return [frames[i] for i in keep], delay


def import_animated_image(theme_dir: str | Path, source: str | Path, w: int, h: int) -> tuple[str, int, int]:
    """Animated widget: frames saved as PNG anim_<stamp>_00.png...; returns (path0, frame_count, delay)."""
    import time
    theme_dir = Path(theme_dir)
    (theme_dir / "images").mkdir(parents=True, exist_ok=True)
    frames, delay = read_gif(source)
    stamp = int(time.time())
    for i, fr in enumerate(frames):
        fr.resize((w, h), Image.Resampling.LANCZOS).save(theme_dir / "images" / f"anim_{stamp}_{i:02d}.png")
    return f"./images/anim_{stamp}_00.png", len(frames), delay


def import_image(theme_dir: str | Path, source: str | Path, w: int, h: int) -> str:
    theme_dir = Path(theme_dir)
    (theme_dir / "images").mkdir(parents=True, exist_ok=True)
    src = Path(source)
    dest = theme_dir / "images" / src.name
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return f"./images/{src.name}"


def renumber_and_tag(theme: SmartMonitorTheme):
    """Sequential ids + one sensor tag per distinct AIDA64 id (vendor tags kept)."""
    counters: dict[int, int] = {}
    used_tags = {w.sensor.fast_sensor for w in theme.widgets
                 if w.sensor and w.sensor.sensor_type_name != AIDA_TYPE and w.sensor.fast_sensor > 0}
    aida_tags: dict[str, int] = {}
    next_tag = 1
    for i, w in enumerate(theme.widgets):
        w.global_id = i
        n = counters.get(w.widget_type, 0)
        counters[w.widget_type] = n + 1
        w.same_type_id = n
        w.object_name = f"{TYPE_NAMES.get(w.widget_type, 'Widget')} {n}"
        w.parent_name = "background"
        if w.sensor and w.sensor.sensor_type_name == AIDA_TYPE:
            key = w.sensor.reading_name
            if key not in aida_tags:
                while next_tag in used_tags:
                    next_tag += 1
                aida_tags[key] = next_tag
                used_tags.add(next_tag)
            w.sensor.fast_sensor = aida_tags[key]
    if len(used_tags) > 250:
        raise ValueError("Trop de capteurs différents dans ce thème (250 max).")


def save_bundle(bundle: SmartMonitorThemeBundle, ui_path: str | Path | None = None) -> Path:
    path = Path(ui_path or bundle.ui_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    renumber_and_tag(bundle.theme)
    write_theme_file(path, bundle.theme)
    bundle.ui_path = str(path)
    bundle.base_dir = str(path.parent)
    return path


def load_bundle(ui_path: str | Path) -> SmartMonitorThemeBundle:
    return parse_theme_bundle(ui_path)


def find_ui(theme_dir: str | Path) -> Path | None:
    files = sorted(Path(theme_dir).glob("*.ui"))
    return files[0] if files else None
