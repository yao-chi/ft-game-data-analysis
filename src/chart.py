# -*- coding: utf-8 -*-
"""
零第三方依赖的 SVG 图表渲染器（仅用标准库）。

为什么自绘而不依赖 matplotlib：让整个分析项目在任何环境都能一键运行，
同时图表以矢量 SVG 输出，可无损嵌入网页报表。
支持：柱状图 / 折线图 / 散点图 / 相关性热力图。
"""
from __future__ import annotations

import html
import math

FONT = "'Microsoft YaHei','PingFang SC','Noto Sans SC',sans-serif"
C_BLUE = "#3E6FF2"
C_ORANGE = "#FF9F1C"
C_GREEN = "#2FD8A8"
C_RED = "#F25757"
C_GRID = "#E8ECF1"
C_AXIS = "#8492A6"
C_TEXT = "#E8ECF8"        # 亮色文字，适配深色报告背景
C_TEXT_DARK = "#1F2329"   # 深色文字（用于浅色填充之上）

W, H = 760, 430
M_L, M_R, M_T, M_B = 64, 24, 66, 56


def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def _header(title: str, sub: str = "") -> str:
    parts = [f'<text x="{M_L}" y="26" class="ttl">{_esc(title)}</text>']
    if sub:
        parts.append(f'<text x="{M_L}" y="46" class="sub">{_esc(sub)}</text>')
    return "".join(parts)


def bar_chart(labels, values, *, title="", sub="", ylabel="", ymin=None, ymax=None,
              color=C_BLUE, fmt=".1f", width=W, height=H, rotate_labels=False) -> str:
    assert len(labels) == len(values)
    pw, ph = width - M_L - M_R, height - M_T - M_B
    vmin = min(values) if ymin is None else ymin
    vmax = max(values) if ymax is None else ymax
    if vmin == vmax:
        vmax = vmin + 1
    pad = (vmax - vmin) * 0.06
    vmin, vmax = vmin - pad, vmax + pad

    def y_pos(v: float) -> float:
        return M_T + ph - (v - vmin) / (vmax - vmin) * ph

    n = len(labels)
    bw = pw / n * 0.62
    # 网格与 y 轴刻度
    grid = []
    ticks = 5
    for i in range(ticks + 1):
        v = vmin + (vmax - vmin) * i / ticks
        y = y_pos(v)
        grid.append(f'<line x1="{M_L}" y1="{y:.1f}" x2="{width - M_R}" y2="{y:.1f}" class="grid"/>')
        grid.append(f'<text x="{M_L - 8}" y="{y + 4:.1f}" class="ax">{v:{fmt}}</text>')
    bars = []
    for i, (lab, v) in enumerate(zip(labels, values)):
        x = M_L + pw * (i + 0.5) / n - bw / 2
        y = y_pos(v)
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" '
                    f'height="{M_T + ph - y:.1f}" rx="3" fill="{color}"/>')
        bars.append(f'<text x="{x + bw / 2:.1f}" y="{y - 7:.1f}" class="val" '
                    f'text-anchor="middle">{v:{fmt}}</text>')
        lx = M_L + pw * (i + 0.5) / n
        if rotate_labels:
            bars.append(f'<text x="{lx:.1f}" y="{height - M_B + 18}" class="ax" '
                        f'text-anchor="end" transform="rotate(38 {lx:.1f} {height - M_B + 18})">'
                        f'{_esc(lab)}</text>')
        else:
            bars.append(f'<text x="{lx:.1f}" y="{height - M_B + 18}" class="ax" '
                        f'text-anchor="middle">{_esc(lab)}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}">'
            f'<style>.ttl{{font:{17}px {FONT};font-weight:700;fill:{C_TEXT}}}'
            f'.sub{{font:12.5px {FONT};fill:{C_AXIS}}}'
            f'.grid{{stroke:{C_GRID};stroke-width:1}}'
            f'.ax{{font:12px {FONT};fill:{C_AXIS};text-anchor:end}}'
            f'.val{{font:12.5px {FONT};fill:{C_TEXT};font-weight:600}}'
            f'</style>'
            f'{_header(title, sub)}'
            f'<text x="{M_L - 8}" y="{M_T - 12}" class="sub" text-anchor="end">{_esc(ylabel)}</text>'
            f'{"".join(grid)}{"".join(bars)}</svg>')


def line_chart(points, *, title="", sub="", xlabel="", ylabel="", xticks=None,
               ymin=None, ymax=None, color=C_BLUE, fmt=".2f", fill=True,
               width=W, height=H, line_w=3) -> str:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    pw, ph = width - M_L - M_R, height - M_T - M_B
    vmin = min(ys) if ymin is None else ymin
    vmax = max(ys) if ymax is None else ymax
    if vmin == vmax:
        vmax = vmin + 1
    pad = (vmax - vmin) * 0.08
    vmin, vmax = vmin - pad, vmax + pad
    xmin, xmax = min(xs), max(xs)

    def xy(x: float, y: float):
        return (M_L + (x - xmin) / (xmax - xmin) * pw,
                M_T + ph - (y - vmin) / (vmax - vmin) * ph)

    grid = []
    for i in range(6):
        v = vmin + (vmax - vmin) * i / 5
        _, y = xy(xmin, v)
        grid.append(f'<line x1="{M_L}" y1="{y:.1f}" x2="{width - M_R}" y2="{y:.1f}" class="grid"/>')
        grid.append(f'<text x="{M_L - 8}" y="{y + 4:.1f}" class="ax">{v:{fmt}}</text>')
    if xticks:
        for tx in xticks:
            ax, _ = xy(tx, vmin)
            grid.append(f'<text x="{ax:.1f}" y="{height - M_B + 18}" class="ax" '
                        f'text-anchor="middle">{_esc(tx)}</text>')

    pairs = [xy(*p) for p in points]
    d = " ".join(f"{a:.1f},{b:.1f}" for a, b in pairs)
    area = ""
    if fill:
        x0, y0 = pairs[0]
        x1, y1 = pairs[-1]
        area = (f'<polygon points="{x0:.1f},{M_T + ph:.1f} {d} '
                f'{x1:.1f},{M_T + ph:.1f}" fill="{color}" opacity="0.12"/>')
    dots = "".join(
        f'<circle cx="{a:.1f}" cy="{b:.1f}" r="3.6" fill="{color}" stroke="#fff" stroke-width="1.2"/>'
        for a, b in pairs)
    ylab = f'<text x="{M_L - 8}" y="{M_T - 12}" class="sub" text-anchor="end">{_esc(ylabel)}</text>'
    xlab = f'<text x="{width / 2}" y="{height - 10}" class="sub" text-anchor="middle">{_esc(xlabel)}</text>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}">'
            f'<style>.ttl{{font:17px {FONT};font-weight:700;fill:{C_TEXT}}}'
            f'.sub{{font:12.5px {FONT};fill:{C_AXIS}}}'
            f'.grid{{stroke:{C_GRID};stroke-width:1}}'
            f'.ax{{font:12px {FONT};fill:{C_AXIS};text-anchor:end}}'
            f'</style>{_header(title, sub)}{ylab}'
            f'{"".join(grid)}{area}'
            f'<polyline points="{d}" fill="none" stroke="{color}" stroke-width="{line_w}" '
            f'stroke-linejoin="round"/>'
            f'{dots}{xlab}</svg>')


def multi_line_chart(series, *, title="", sub="", xlabel="", ylabel="", xticks=None,
                     ymin=None, ymax=None, fmt=".1f", width=W, height=H,
                     line_w=3, legend=True) -> str:
    """多条折线对比。series: list[dict(xs, ys, color, label)]"""
    xs_all = [p for s in series for p in s["xs"]]
    ys_all = [p for s in series for p in s["ys"]]
    pw, ph = width - M_L - M_R, height - M_T - M_B
    vmin = min(ys_all) if ymin is None else ymin
    vmax = max(ys_all) if ymax is None else ymax
    if vmin == vmax:
        vmax = vmin + 1
    pad = (vmax - vmin) * 0.08
    vmin, vmax = vmin - pad, vmax + pad
    xmin, xmax = min(xs_all), max(xs_all)

    def xy(x: float, y: float):
        return (M_L + (x - xmin) / (xmax - xmin) * pw,
                M_T + ph - (y - vmin) / (vmax - vmin) * ph)

    grid = []
    for i in range(6):
        v = vmin + (vmax - vmin) * i / 5
        _, y = xy(xmin, v)
        grid.append(f'<line x1="{M_L}" y1="{y:.1f}" x2="{width - M_R}" y2="{y:.1f}" class="grid"/>')
        grid.append(f'<text x="{M_L - 8}" y="{y + 4:.1f}" class="ax">{v:{fmt}}</text>')
    if xticks:
        for tx in xticks:
            ax, _ = xy(tx, vmin)
            grid.append(f'<text x="{ax:.1f}" y="{height - M_B + 18}" class="ax" '
                        f'text-anchor="middle">{_esc(tx)}</text>')

    lines, dots = [], []
    for s in series:
        pairs = [xy(x, y) for x, y in zip(s["xs"], s["ys"])]
        d = " ".join(f"{a:.1f},{b:.1f}" for a, b in pairs)
        lines.append(f'<polyline points="{d}" fill="none" stroke="{s["color"]}" '
                     f'stroke-width="{line_w}" stroke-linejoin="round"/>')
        dots += [f'<circle cx="{a:.1f}" cy="{b:.1f}" r="3" fill="{s["color"]}"/>'
                 for a, b in pairs]
    ylab = f'<text x="{M_L - 8}" y="{M_T - 12}" class="sub" text-anchor="end">{_esc(ylabel)}</text>'
    xlab = f'<text x="{width / 2}" y="{height - 10}" class="sub" text-anchor="middle">{_esc(xlabel)}</text>'
    legend_svg = ""
    if legend:
        lx = width - M_R - 170
        leg = []
        for i, s in enumerate(series):
            ly = M_T + 8 + i * 20
            leg.append(f'<rect x="{lx}" y="{ly - 12}" width="14" height="14" rx="3" fill="{s["color"]}"/>'
                       f'<text x="{lx + 20}" y="{ly - 1}" class="ax" text-anchor="start">{_esc(s["label"])}</text>')
        legend_svg = "".join(leg)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}">'
            f'<style>.ttl{{font:17px {FONT};font-weight:700;fill:{C_TEXT}}}'
            f'.sub{{font:12.5px {FONT};fill:{C_AXIS}}}'
            f'.grid{{stroke:{C_GRID};stroke-width:1}}'
            f'.ax{{font:12px {FONT};fill:{C_AXIS};text-anchor:end}}'
            f'</style>{_header(title, sub)}{ylab}'
            f'{"".join(grid)}{"".join(lines)}{"".join(dots)}{legend_svg}{xlab}</svg>')


def scatter_chart(points, *, title="", sub="", xlabel="", ylabel="", xticks=None,
                  yticks=None, label_top=8, color=C_ORANGE, width=W, height=H,
                  fmt=".1f") -> str:
    """points: list[dict(x, y, size?, label?)]"""
    xs = [p["x"] for p in points]
    ys = [p["y"] for p in points]
    pw, ph = width - M_L - M_R, height - M_T - M_B
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    if xmin == xmax:
        xmax = xmin + 1
    padx = (xmax - xmin) * 0.08
    pady = (ymax - ymin) * 0.12
    xmin, xmax = xmin - padx, xmax + padx
    ymin, ymax = ymin - pady, ymax + pady

    def xy(x: float, y: float):
        return (M_L + (x - xmin) / (xmax - xmin) * pw,
                M_T + ph - (y - ymin) / (ymax - ymin) * ph)

    grid = []
    for v in ([ymin + (ymax - ymin) * i / 5 for i in range(6)] if yticks is None else yticks):
        _, y = xy(xmin, v)
        grid.append(f'<line x1="{M_L}" y1="{y:.1f}" x2="{width - M_R}" y2="{y:.1f}" class="grid"/>')
        grid.append(f'<text x="{M_L - 8}" y="{y + 4:.1f}" class="ax">{v:{fmt}}</text>')
    if xticks:
        for tx in xticks:
            ax, _ = xy(tx, ymin)
            grid.append(f'<text x="{ax:.1f}" y="{height - M_B + 18}" class="ax" '
                        f'text-anchor="middle">{_esc(tx)}</text>')
    scored = sorted(points, key=lambda p: p.get("size", 8), reverse=True)
    targets = {id(p) for p in scored[:label_top]}
    circs, labs = [], []
    for p in points:
        a, b = xy(p["x"], p["y"])
        r = p.get("size", 8) * 0.55 + 4
        circs.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="{r:.1f}" fill="{color}" '
                     f'opacity="0.78"/>')
        if id(p) in targets and p.get("label"):
            labs.append(f'<text x="{a:.1f}" y="{b - r - 4:.1f}" class="lab" '
                        f'text-anchor="middle">{_esc(p["label"])}</text>')
    ylab = f'<text x="{M_L - 8}" y="{M_T - 12}" class="sub" text-anchor="end">{_esc(ylabel)}</text>'
    xlab = f'<text x="{width / 2}" y="{height - 10}" class="sub" text-anchor="middle">{_esc(xlabel)}</text>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}">'
            f'<style>.ttl{{font:17px {FONT};font-weight:700;fill:{C_TEXT}}}'
            f'.sub{{font:12.5px {FONT};fill:{C_AXIS}}}'
            f'.grid{{stroke:{C_GRID};stroke-width:1}}'
            f'.ax{{font:12px {FONT};fill:{C_AXIS};text-anchor:end}}'
            f'.lab{{font:12px {FONT};fill:{C_TEXT};font-weight:600}}'
            f'</style>{_header(title, sub)}{ylab}'
            f'{"".join(grid)}{"".join(circs)}{"".join(labs)}{xlab}</svg>')


def heatmap(matrix, row_labels, col_labels, *, title="", sub="", width=W, height=None,
            vmin=-1.0, vmax=1.0, cell=46) -> str:
    nr, nc = len(matrix), len(matrix[0])
    top = 66
    plot_w = nc * cell
    max_row_len = max(len(str(l)) for l in row_labels)
    left = max(46, 14 + int(max_row_len * 7.6))   # 行标签自适应宽度（英文标签更长）
    plot_h = nr * cell
    total_w = left + plot_w + 16
    total_h = top + plot_h + 58

    def color_of(v: float) -> tuple[str, str]:
        """返回 (填充色, 文字色)；文字色按底色亮度自适应（>170 用深字）。"""
        t = (v - vmin) / (vmax - vmin)
        if v >= 0:
            r = int(62 + (255 - 62) * (1 - t))
            g = int(111 + (255 - 111) * (1 - t))
            b = int(242 + (255 - 242) * (1 - t))
        else:
            r = 242
            g = int(87 + (255 - 87) * (1 - (t * 2)))
            b = int(87 + (255 - 87) * (1 - (t * 2)))
        fill = f"rgb({r},{g},{b})"
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        txt_col = C_TEXT_DARK if lum > 170 else "#FFFFFF"
        return fill, txt_col

    grid = []
    for r in range(nr):
        for c in range(nc):
            v = matrix[r][c]
            x = left + c * cell
            y = top + r * cell
            fill, txt_col = color_of(v)
            grid.append(f'<rect x="{x}" y="{y}" width="{cell - 1}" height="{cell - 1}" '
                        f'fill="{fill}" rx="2"/>')
            grid.append(f'<text x="{x + (cell - 1) / 2:.1f}" y="{y + (cell - 1) / 2 + 4:.1f}" '
                        f'class="cv" fill="{txt_col}" text-anchor="middle">{v:+.2f}</text>')
    for c, lab in enumerate(col_labels):
        x = left + c * cell + (cell - 1) / 2
        grid.append(f'<text x="{x:.1f}" y="{top - 8}" class="cl" text-anchor="middle">{_esc(lab)}</text>')
    for r, lab in enumerate(row_labels):
        y = top + r * cell + (cell - 1) / 2
        grid.append(f'<text x="{left - 8}" y="{y + 4:.1f}" class="cl" text-anchor="end">{_esc(lab)}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w} {total_h}" '
            f'width="{total_w}" height="{total_h}">'
            f'<style>.ttl{{font:17px {FONT};font-weight:700;fill:{C_TEXT}}}'
            f'.sub{{font:12.5px {FONT};fill:{C_AXIS}}}'
            f'.cl{{font:12.5px {FONT};fill:{C_TEXT}}}'
            f'.cv{{font:12px {FONT}}}'
            f'</style>{_header(title, sub)}{"".join(grid)}</svg>')