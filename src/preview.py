"""Renderiza uma prévia estática dos resultados, sem dependências externas."""

from collections import Counter
from html import escape
from math import ceil

INK = "#252037"
MUTED = "#625A72"
PURPLE = "#6335A5"
PINK = "#A42C64"


def number(value, decimals=0):
    return f"{value:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def text(x, y, value, size=16, color=MUTED, weight=400, anchor="start"):
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" '
        f'text-anchor="{anchor}">{escape(str(value))}</text>'
    )


def box(x, y, w, h, color="#FFFFFF", radius=15):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{color}" rx="{radius}"/>'


def line(x1, y1, x2, y2, color, width=1):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"/>'


def write_preview(path, catalog, sales, forecast, backtest):
    product_brands = {p["produto_id"]: p["marca"] for p in catalog}
    brands, months, future = Counter(), Counter(), Counter()
    for sale in sales:
        brands[product_brands[sale["produto_id"]]] += sale["receita_liquida"]
        months[sale["data"].strftime("%Y-%m")] += sale["quantidade"]
    for row in forecast:
        future[row["mes"].strftime("%Y-%m")] += row["unidades_previstas"]
    revenue = sum(brands.values())
    orders = len({sale["pedido_id"] for sale in sales})
    wape = sum(row["erro_absoluto"] for row in backtest) / sum(row["unidades_reais"] for row in backtest)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 650" width="1200" height="650" '
        'role="img" aria-labelledby="title description" font-family="Segoe UI, Arial, sans-serif">',
        '<title id="title">Beauty Commerce Analytics</title>',
        '<desc id="description">Indicadores de e-commerce simulado, ranking de marcas e série de '
        'unidades vendidas até dezembro de 2025, com projeção de janeiro a março de 2026.</desc>',
        box(0, 0, 1200, 650, "#F7F3FA", 22),
        box(24, 24, 1152, 140, "#29203F", 18),
        text(52, 59, "PORTFÓLIO DE DADOS     /     E-COMMERCE", 14, "#E1CCFA", 700),
        text(52, 108, "Beauty Commerce Analytics", 42, "#FFFFFF", 700),
        text(53, 138, "Vendas simuladas · jan/2024 a dez/2025", 16, "#E1CCFA"),
        box(953, 47, 194, 34, "#503867", 17),
        text(1050, 69, "DADOS SINTÉTICOS", 13, "#FFFFFF", 700, "middle"),
    ]
    for i, (label, value) in enumerate((
        ("Receita líquida", f"R$ {number(revenue, 2)}"), ("Pedidos", number(orders)),
        ("Unidades vendidas", number(sum(months.values()))), ("Ticket médio", f"R$ {number(revenue / orders, 2)}"),
    )):
        x = 24 + i * 292
        parts.extend((box(x, 182, 276, 96), text(x + 18, 213, label, 15), text(x + 18, 251, value, 27, INK, 700)))
    parts.extend((
        box(24, 296, 392, 287), box(434, 296, 742, 287),
        text(46, 334, "Receita por marca", 20, INK, 700),
        text(46, 357, "Ranking das marcas fictícias", 13),
        text(456, 334, "Vendas e previsão de demanda", 20, INK, 700),
        text(456, 357, f"Unidades por mês · erro no teste: {number(wape * 100, 1)}% (WAPE por categoria)", 13),
    ))
    max_revenue = max(brands.values())
    for i, (brand, amount) in enumerate(brands.most_common()):
        y = 387 + i * 47
        parts.extend((
            text(46, y, brand, 14, INK, 600),
            text(393, y, f"R$ {number(amount, 2)}", 13, MUTED, anchor="end"),
            box(46, y + 8, 347, 8, "#F1EAF7", 4),
            box(46, y + 8, round(float(347 * amount / max_revenue), 2), 8, PURPLE, 4),
        ))
    actual = sorted(months.items())
    estimates = sorted(future.items())
    series = actual + estimates
    upper = ceil(max(value for _, value in series) / 100) * 100
    chart_x, chart_right, chart_top, chart_bottom = 495, 1149, 395, 512
    step = (chart_right - chart_x) / (len(series) - 1)

    def coords(i, value):
        return round(chart_x + i * step, 2), round(chart_bottom - value / upper * (chart_bottom - chart_top), 2)

    boundary = round(chart_x + step * (len(actual) - 0.5), 2)
    parts.append(box(boundary, chart_top, round(chart_right - boundary, 2), chart_bottom - chart_top, "#F8EBF3", 0))
    for value in (0, upper // 2, upper):
        _, y = coords(0, value)
        parts.extend((line(chart_x, y, chart_right, y, "#E6DEED"), text(486, y + 4, number(value), 11, anchor="end")))
    for i, (color, offset, values, dashed) in enumerate((
        (PURPLE, 0, actual, ""), (PINK, len(actual) - 1, actual[-1:] + estimates, ' stroke-dasharray="6 5"'),
    )):
        points = " ".join(f"{x},{y}" for x, y in (coords(offset + j, v) for j, (_, v) in enumerate(values)))
        parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="3" '
                     f'stroke-linejoin="round" stroke-linecap="round"{dashed}/>')
        legend_x = 456 + i * 138
        parts.extend((
            line(legend_x, 561, legend_x + 22, 561, color, 3),
            text(legend_x + 30, 565, ("Vendas reais*", "Previsão")[i], 13),
        ))
    for index, label in ((0, "jan/24"), (6, "jul/24"), (12, "jan/25"), (18, "jul/25"), (24, "jan/26")):
        x, _ = coords(index, 0)
        parts.append(text(x, 532, label, 11, anchor="middle"))
    parts.extend((
        text(26, 615, "* Vendas observadas no cenário simulado. Prévia estática gerada pelo pipeline Python.", 13),
        "</svg>",
    ))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8", newline="\n")
