"""Shared Praganya Construction letterhead for every client-facing PDF.

Rules (agreed with the owner):
  * header band (logo, firm name, services, proprietor + phone) on the FIRST page only
  * footer on EVERY page: a straight line, then "Praganya Construction" centred
  * no barcode / QR, no invented address, no fake seal or signature
  * client name and date are typed by the user - never pre-filled
Works with a raw reportlab canvas (``first_page`` / ``later_page``) and with
platypus (``on_first`` / ``on_later`` page callbacks).
"""
from __future__ import annotations

import os

from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader

NAVY = HexColor("#1E3A8A")
GOLD = HexColor("#F59E0B")
GREY = HexColor("#64748B")
FIRM = "Praganya Construction"
_ASSETS = os.path.join(os.path.dirname(__file__), "assets")
_HEADER = os.path.join(_ASSETS, "letterhead_header.png")
_img = None


def _band() -> ImageReader | None:
    global _img
    if _img is None and os.path.exists(_HEADER):
        _img = ImageReader(_HEADER)
    return _img


def header_height(page_w: float, margin: float = 28) -> float:
    im = _band()
    if not im:
        return 40.0
    w, h = im.getSize()
    return (page_w - 2 * margin) * h / w


def header(c, page_w: float, page_h: float, margin: float = 28, top: float = 18) -> float:
    """Draw the header band; return the y (from page bottom) just below it."""
    im = _band()
    hh = header_height(page_w, margin)
    y = page_h - top - hh
    if im:
        c.drawImage(im, margin, y, width=page_w - 2 * margin, height=hh, mask="auto")
    else:  # asset missing - plain text fallback, never fails the PDF
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(page_w / 2, page_h - top - 22, FIRM.upper())
        c.setStrokeColor(GOLD)
        c.line(margin, y, page_w - margin, y)
    return y


def footer(c, page_w: float, margin: float = 28, base: float = 22) -> None:
    c.saveState()
    c.setStrokeColor(NAVY)
    c.setLineWidth(0.8)
    c.line(margin, base + 14, page_w - margin, base + 14)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(page_w / 2, base + 2, FIRM)
    c.restoreState()


def client_block(c, y: float, page_w: float, client: str = "", date: str = "", margin: float = 28) -> float:
    """Client + date lines, typed by the user. Empty values leave a blank line."""
    c.saveState()
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin, y, "Client:")
    c.drawRightString(page_w - margin - 120, y, "Date:")
    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor("#0F172A"))
    c.setStrokeColor(GREY)
    c.setLineWidth(0.4)
    c.drawString(margin + 38, y, client or "")
    c.line(margin + 36, y - 2, page_w - margin - 140, y - 2)
    c.drawString(page_w - margin - 114, y, date or "")
    c.line(page_w - margin - 116, y - 2, page_w - margin, y - 2)
    c.restoreState()
    return y - 22


SEAL_W, SEAL_H = 170.0, 64.0


def seal_box(c, page_w: float, y: float, margin: float = 28, w: float = SEAL_W, h: float = SEAL_H) -> None:
    """ONE blank box, right corner, labelled "Seal & Signature". y = bottom of box.

    Reserve SEAL_H + 16 pt above the footer (y >= 52) so it never overlaps content/footer."""
    c.saveState()
    c.setStrokeColor(GREY)
    c.setLineWidth(0.6)
    x = page_w - margin - w
    c.rect(x, y, w, h)
    c.setFont("Helvetica", 8)
    c.setFillColor(GREY)
    c.drawCentredString(x + w / 2, y - 10, "Seal & Signature")
    c.restoreState()


seal_boxes = lambda c, x, y, *a, **k: None  # retired: two boxes replaced by seal_box


try:  # platypus flowable: right-aligned, kept together, flows after the body (no overlap)
    from reportlab.platypus import Flowable

    class SealSignature(Flowable):
        def __init__(self, width: float):
            super().__init__()
            self.width, self.height = width, SEAL_H + 14

        def wrap(self, aw, ah):
            self.width = aw
            return aw, self.height

        def draw(self):
            c = self.canv
            c.saveState()
            c.setStrokeColor(GREY)
            c.setLineWidth(0.6)
            x = self.width - SEAL_W
            c.rect(x, 14, SEAL_W, SEAL_H)
            c.setFont("Helvetica", 8)
            c.setFillColor(GREY)
            c.drawCentredString(x + SEAL_W / 2, 3, "Seal & Signature")
            c.restoreState()
except Exception:  # pragma: no cover
    SealSignature = None


# ---- canvas helpers ------------------------------------------------------
def first_page(c, page_w, page_h, margin=28, client="", date="", with_client=False) -> float:
    y = header(c, page_w, page_h, margin)
    footer(c, page_w, margin)
    if with_client:
        y = client_block(c, y - 22, page_w, client, date, margin)
    return y


def later_page(c, page_w, margin=28) -> None:
    footer(c, page_w, margin)


# ---- platypus callbacks --------------------------------------------------
def on_first(page_w, page_h, margin=28):
    def _cb(canvas, doc):
        first_page(canvas, page_w, page_h, margin)
    return _cb


def on_later(page_w, margin=28):
    def _cb(canvas, doc):
        later_page(canvas, page_w, margin)
    return _cb
