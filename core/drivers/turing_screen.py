"""Écrans série (Turing, XuanFang, Kipye, WeAct) via les pilotes de turing-smart-screen-python (GPL-3.0)."""
from __future__ import annotations

from PIL import Image

from . import ImageScreen


class TuringScreen(ImageScreen):
    def __init__(self, revision: str, width: int, height: int):
        self.revision = revision
        self.portrait = (width, height)
        self.lcd = None
        self.name = f"Turing {revision}"
        self.max_fps = 2.0 if revision in ("A", "B", "D") else 6.0

    def open(self):
        from .turing import lcd_comm
        w, h = self.portrait
        if self.revision == "A":
            from .turing.lcd_comm_rev_a import LcdCommRevA as Cls
        elif self.revision == "B":
            from .turing.lcd_comm_rev_b import LcdCommRevB as Cls
        elif self.revision == "C":
            from .turing.lcd_comm_rev_c import LcdCommRevC as Cls
        elif self.revision == "D":
            from .turing.lcd_comm_rev_d import LcdCommRevD as Cls
        elif self.revision == "WEACT_A":
            from .turing.lcd_comm_weact_a import LcdCommWeActA as Cls
        else:
            from .turing.lcd_comm_weact_b import LcdCommWeActB as Cls
        lcd = Cls(com_port="AUTO", display_width=w, display_height=h, update_queue=None)
        lcd.Reset()
        lcd.InitializeComm()
        lcd.SetBrightness(level=40)
        try:
            lcd.SetBackplateLedColor(led_color=(255, 255, 255))
        except Exception:
            pass
        landscape = w < h
        lcd.SetOrientation(orientation=lcd_comm.Orientation.LANDSCAPE if landscape else lcd_comm.Orientation.PORTRAIT)
        self.lcd = lcd

    def close(self):
        if self.lcd is not None:
            try:
                self.lcd.closeSerial()
            except Exception:
                pass
        self.lcd = None

    @property
    def size(self) -> tuple[int, int]:
        w, h = self.portrait
        return (max(w, h), min(w, h)) if w != h else (w, h)

    def show(self, image: Image.Image):
        if self.lcd is None:
            self.open()
        self.lcd.DisplayPILImage(image, 0, 0)
