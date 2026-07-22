"""PDF export: the station×band matrix on A4 landscape, fit to width (§10.4).

Layout: WLD-styled header (navy band with the WLD lettermark), field day
metadata, summary statistics, legend, and the full matrix. The matrix
always fits the page width; with very many bands the band columns are
split into groups over consecutive pages. Long station lists continue on
extra pages with a repeated header row.

Core PDF fonts are Latin-1 only, so the non-color status markers are
letters (see MARKERS), never unicode symbols like a check mark — those
would render as black boxes.
"""

from __future__ import annotations

from datetime import timezone

from fpdf import FPDF

from app.core.callsign import normalize_callsign
from app.core.models import utc_now
from app.core.status import Status
from app.core.sync_engine import SyncEngine

# WLD house style
NAVY = (5, 13, 26)
TEAL = (0, 180, 204)
INK = (26, 35, 50)
LINE = (222, 226, 230)

# Non-color markers (Latin-1 safe; the color-blind/sunlight backup)
MARKERS = {
    Status.NOT_WORKED: "",
    Status.WORKED_BY_N1MM: "X",
    Status.MANUAL_WORKED: "M",
    Status.MANUAL_NOT_WORKED: "m",
    Status.EXCLUDED: "-",
}

LEGEND_LABELS = {
    Status.NOT_WORKED: "Not worked",
    Status.WORKED_BY_N1MM: "X  Worked (N1MM)",
    Status.MANUAL_WORKED: "M  Worked (manual)",
    Status.MANUAL_NOT_WORKED: "m  Not worked (manual)",
    Status.EXCLUDED: "-  Excluded",
}

MAX_BANDS_PER_PAGE = 12
CALL_COL_MM = 42
CAT_COL_MM = 52
ROW_MM = 6.2
MARGIN_MM = 10


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = (value or "#FFFFFF").lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore
    except ValueError:
        return (255, 255, 255)


def _latin1(text: str) -> str:
    return str(text).encode("latin-1", "replace").decode("latin-1")


class _MatrixPdf(FPDF):
    def __init__(self) -> None:
        super().__init__(orientation="L", unit="mm", format="A4")
        self.set_auto_page_break(auto=False)
        self.set_margins(MARGIN_MM, MARGIN_MM, MARGIN_MM)


def build_pdf(engine: SyncEngine) -> bytes:
    """Render the matrix report; returns the PDF as bytes."""
    fieldday = engine.fieldday
    bands = list(fieldday.selected_bands)
    colors = {s: _hex_to_rgb(fieldday.status_colors.get(s.value, "#FFFFFF"))
              for s in Status}

    strict = fieldday.strict_callsign_matching
    stations = []
    for station in engine.stations:
        if not station.active:
            continue
        normalized = normalize_callsign(station.original_callsign, strict=strict)
        if normalized is None or engine.station_index.get(normalized) is not station:
            continue
        stations.append((station, normalized))

    pdf = _MatrixPdf()
    page_width = pdf.w - 2 * MARGIN_MM

    band_groups = [bands[i:i + MAX_BANDS_PER_PAGE]
                   for i in range(0, len(bands), MAX_BANDS_PER_PAGE)] or [[]]

    worked = sum(
        1 for (_, normalized) in stations for band in bands
        if (cell := engine.get_cell(normalized, band)) is not None
        and cell.status in (Status.WORKED_BY_N1MM, Status.MANUAL_WORKED)
    )
    total = len(stations) * len(bands)

    def header(with_meta: bool) -> None:
        pdf.add_page()
        # WLD-band
        pdf.set_fill_color(*NAVY)
        pdf.rect(0, 0, pdf.w, 16, style="F")
        pdf.set_xy(MARGIN_MM, 4)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(16, 8, "WLD")
        pdf.set_draw_color(*TEAL)
        pdf.set_line_width(0.8)
        pdf.line(MARGIN_MM + 15, 4, MARGIN_MM + 15, 12)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, _latin1(f"  {fieldday.name} - Field Day Tracker"))
        pdf.set_line_width(0.2)
        pdf.set_text_color(*INK)
        pdf.set_y(20)

        if with_meta:
            pdf.set_font("Helvetica", "", 9.5)
            meta = " | ".join(filter(None, [
                fieldday.location,
                fieldday.event_callsign,
                fieldday.organizer_club,
                f"{fieldday.start_utc:%Y-%m-%d %H:%M} - "
                f"{fieldday.end_utc:%Y-%m-%d %H:%M} UTC",
                f"Bands: {', '.join(bands)}",
                f"Exported: {utc_now():%Y-%m-%d %H:%M} UTC",
            ]))
            pdf.cell(0, 5, _latin1(meta), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "B", 9.5)
            pdf.cell(0, 5,
                     _latin1(f"Stations: {len(stations)}   "
                             f"Worked: {worked} / {total} combinations"),
                     new_x="LMARGIN", new_y="NEXT")
            # Legende
            pdf.set_font("Helvetica", "", 8.5)
            x = MARGIN_MM
            y = pdf.get_y() + 1
            for status in Status:
                pdf.set_fill_color(*colors[status])
                pdf.set_draw_color(*LINE)
                pdf.rect(x, y, 4, 4, style="DF")
                pdf.set_xy(x + 5, y)
                label = _latin1(LEGEND_LABELS[status])
                pdf.cell(pdf.get_string_width(label) + 2, 4, label)
                x += 5 + pdf.get_string_width(label) + 8
            pdf.set_y(y + 7)

    def matrix_header_row(group: list[str], band_width: float) -> None:
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_fill_color(*NAVY)
        pdf.set_text_color(255, 255, 255)
        pdf.set_draw_color(*LINE)
        pdf.cell(CALL_COL_MM, ROW_MM, "Callsign", border=1, fill=True)
        pdf.cell(CAT_COL_MM, ROW_MM, "Category / Section", border=1, fill=True)
        for band in group:
            pdf.cell(band_width, ROW_MM, band, border=1, fill=True, align="C")
        pdf.ln(ROW_MM)
        pdf.set_text_color(*INK)

    for group_index, group in enumerate(band_groups):
        band_width = ((page_width - CALL_COL_MM - CAT_COL_MM) / max(len(group), 1))
        header(with_meta=(group_index == 0))
        matrix_header_row(group, band_width)

        pdf.set_font("Helvetica", "", 8.5)
        for station, normalized in stations:
            if pdf.get_y() + ROW_MM > pdf.h - MARGIN_MM:
                header(with_meta=False)
                matrix_header_row(group, band_width)
                pdf.set_font("Helvetica", "", 8.5)
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.cell(CALL_COL_MM, ROW_MM, _latin1(station.original_callsign),
                     border=1)
            pdf.set_font("Helvetica", "", 7.5)
            cat = station.category or ""
            if station.section:
                cat = f"{cat} / {station.section}" if cat else station.section
            pdf.cell(CAT_COL_MM, ROW_MM, _latin1(cat[:44]), border=1)
            pdf.set_font("Helvetica", "B", 8.5)
            for band in group:
                cell = engine.get_cell(normalized, band)
                status = cell.status if cell else Status.NOT_WORKED
                pdf.set_fill_color(*colors[status])
                # Donkere celvulling → witte letter
                r, g, b = colors[status]
                bright = (r * 299 + g * 587 + b * 114) / 1000
                pdf.set_text_color(255, 255, 255) if bright < 128 else \
                    pdf.set_text_color(*INK)
                pdf.cell(band_width, ROW_MM, MARKERS[status], border=1,
                         fill=True, align="C")
            pdf.set_text_color(*INK)
            pdf.ln(ROW_MM)

    return bytes(pdf.output())
