"""Gera CSVs de origem, limpa as vendas e estima a demanda mensal."""

import argparse
import csv
import random
from collections import Counter
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from statistics import mean

from src.preview import write_preview

ROOT = Path(__file__).resolve().parents[1]
START = date(2024, 1, 1)
END = date(2025, 12, 31)
CENT = Decimal("0.01")
CATEGORIES = (
    ("pele", "Cuidados com a pele"),
    ("cabelo", "Cuidados capilares"),
    ("make", "Maquiagem"),
    ("fragrancia", "Fragrâncias"),
)
PRODUCTS = (
    ("pele", "Nuvem Clara", "Sérum hidratante", 69),
    ("pele", "Nuvem Clara", "Gel de limpeza", 39),
    ("pele", "Verde Âmbar", "Protetor facial", 79),
    ("pele", "Rosa de Vidro", "Máscara facial", 49),
    ("cabelo", "Verde Âmbar", "Shampoo nutritivo", 45),
    ("cabelo", "Verde Âmbar", "Óleo capilar", 62),
    ("cabelo", "Nuvem Clara", "Condicionador leve", 42),
    ("cabelo", "Estúdio Aurora", "Máscara capilar", 75),
    ("make", "Estúdio Aurora", "Duo de blush", 55),
    ("make", "Rosa de Vidro", "Batom acetinado", 36),
    ("make", "Rosa de Vidro", "Base fluida", 89),
    ("make", "Nuvem Clara", "Gel para sobrancelhas", 33),
    ("fragrancia", "Rosa de Vidro", "Body splash floral", 68),
    ("fragrancia", "Verde Âmbar", "Colônia cítrica", 99),
    ("fragrancia", "Estúdio Aurora", "Fragrância âmbar", 129),
    ("fragrancia", "Estúdio Aurora", "Mini perfume", 59),
)
CHANNELS = ("Loja própria", "Marketplace", "Social commerce")
METHODS = {"Media 3 meses": "Média dos últimos 3 meses", "Sazonal": "Sazonal com ajuste de nível"}
SALES_FIELDS = (
    "pedido_id", "item", "data", "produto_id", "categoria_id", "canal", "quantidade",
    "preco_unitario", "desconto_pct", "receita_liquida",
)


def dates(start, end):
    return (start + timedelta(days=i) for i in range((end - start).days + 1))


def add_months(day, offset):
    year, month = divmod(day.year * 12 + day.month - 1 + offset, 12)
    return date(year, month + 1, 1)


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def generate_raw(folder, seed):
    rng = random.Random(seed)
    products = [
        dict(produto_id=f"P{i:02d}", categoria_id=category, marca=brand, produto=product, preco=price)
        for i, (category, brand, product, price) in enumerate(PRODUCTS, start=1)
    ]
    write_csv(folder / "catalogo.csv", products[0], products)
    orders = []
    order = 0
    for day in dates(START, END):
        high_season = day.month in (5, 11, 12)
        daily_volume = (
            3.5 + 1.1 * (day.year - START.year) + (0.6 if day.weekday() >= 5 else 0)
            + (2.5 if day.month == 11 else 0.9 if high_season else 0)
        )
        for _ in range(max(1, round(rng.gauss(daily_volume, 1.35)))):
            order += 1
            channel = rng.choices(CHANNELS, weights=(6, 3, 2))[0]
            size = rng.choices((1, 2, 3), weights=(70, 25, 5))[0]
            available = products.copy()
            for item in range(1, size + 1):
                weights = [product_weight(p, day, channel) for p in available]
                product = rng.choices(available, weights=weights)[0]
                available.remove(product)
                orders.append({
                    "pedido_id": f"V{order:06d}", "item": item, "data": day,
                    "produto_id": product["produto_id"], "canal": channel,
                    "quantidade": rng.choices((1, 2, 3), weights=(83, 14, 3))[0],
                    "preco_unitario": product["preco"],
                    "desconto_pct": rng.choices((0, 5, 10, 15, 20), weights=(
                        (21, 17, 26, 22, 14) if high_season else (55, 20, 15, 7, 3)
                    ))[0],
                })
    write_csv(folder / "pedidos.csv", orders[0], orders)


def product_weight(product, day, channel):
    category = product["categoria_id"]
    if category == "fragrancia":
        return 2.1 if day.month in (5, 11, 12) else 0.85
    if category == "pele":
        return 1.6 if day.month in (1, 2, 10, 11, 12) else 1.25
    if category == "cabelo":
        return 1.65 if day.month in (6, 7, 8) else 1.10
    return 1.65 if channel == "Social commerce" else 1.0


def money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def clean_sales(raw_folder):
    catalog = read_csv(raw_folder / "catalogo.csv")
    categories = {identifier for identifier, _ in CATEGORIES}
    products = {row["produto_id"]: row for row in catalog}
    if not catalog or len(products) != len(catalog) or any(
        row["categoria_id"] not in categories for row in catalog
    ):
        raise ValueError("Catálogo inválido: chave de produto duplicada ou categoria desconhecida.")
    result = []
    item_keys = set()
    order_meta = {}
    for raw in read_csv(raw_folder / "pedidos.csv"):
        product = products.get(raw["produto_id"])
        if product is None:
            raise ValueError(f"Produto desconhecido: {raw['produto_id']}")
        day = date.fromisoformat(raw["data"])
        units, item = int(raw["quantidade"]), int(raw["item"])
        price, discount = money(raw["preco_unitario"]), int(raw["desconto_pct"])
        key = raw["pedido_id"], item
        meta = day, raw["canal"]
        if (
            not raw["pedido_id"] or key in item_keys or item < 1 or units < 1
            or price <= 0 or not 0 <= discount <= 100 or not START <= day <= END
            or raw["canal"] not in CHANNELS or order_meta.setdefault(raw["pedido_id"], meta) != meta
        ):
            raise ValueError(f"Item de venda inválido: {key}")
        item_keys.add(key)
        result.append({
            **raw, "item": item, "data": day, "quantidade": units, "preco_unitario": price,
            "desconto_pct": discount, "categoria_id": product["categoria_id"],
            "receita_liquida": money(price * units * (Decimal(100) - discount) / 100),
        })
    if not result:
        raise ValueError("Nenhuma venda disponível.")
    return catalog, result


def forecast_values(history, method, horizon):
    if horizon < 1 or (method == "Sazonal" and (len(history) < 15 or horizon > 12)):
        raise ValueError("Histórico ou horizonte insuficiente para a previsão.")
    if method == "Media 3 meses" and len(history) >= 3:
        return [round(mean(history[-3:]))] * horizon
    if method != "Sazonal":
        raise ValueError(f"Método desconhecido ou histórico insuficiente: {method}")
    prior = sum(history[-15:-12])
    growth = sum(history[-3:]) / prior if prior else 1
    growth = min(1.5, max(0.65, growth))
    return [max(0, round(value * growth)) for value in history[-12:][:horizon]]


def absolute_error(actual, predicted):
    return sum(abs(real - estimate) for real, estimate in zip(actual, predicted, strict=True))


def forecast_demand(sales):
    history_months = [add_months(START, i) for i in range(24)]
    monthly = Counter()
    for row in sales:
        monthly[row["categoria_id"], row["data"].replace(day=1)] += row["quantidade"]
    forecast = []
    backtest = []
    for category, _ in CATEGORIES:
        history = [monthly[category, month] for month in history_months]
        # Jul–Set/2025 seleciona o método. Out–Dez/2025 mede o resultado em período separado.
        training, validation, test = history[:18], history[18:21], history[21:]
        method = min(METHODS, key=lambda m: absolute_error(validation, forecast_values(training, m, 3)))
        for month, real, estimate in zip(
            history_months[21:], test, forecast_values(history[:21], method, 3), strict=True
        ):
            backtest.append({
                "mes": month, "categoria_id": category, "metodo": METHODS[method],
                "unidades_reais": real, "unidades_previstas": estimate, "erro_absoluto": abs(real - estimate),
            })
        future = forecast_values(history, method, 3)
        for i, estimate in enumerate(future, start=1):
            forecast.append({
                "mes": add_months(END, i), "categoria_id": category,
                "unidades_previstas": estimate, "metodo": METHODS[method],
            })
    return forecast, backtest


def build(root, seed=42):
    raw = root / "data" / "raw"
    curated = root / "data" / "curated"
    generate_raw(raw, seed)
    catalog, sales = clean_sales(raw)
    forecast, backtest = forecast_demand(sales)
    last_month = max(row["mes"] for row in forecast)
    last_day = add_months(last_month, 1) - timedelta(days=1)
    write_csv(curated / "vendas.csv", SALES_FIELDS, sales)
    product_fields = ("produto_id", "marca", "produto")
    write_csv(curated / "produtos.csv", product_fields, (
        {field: row[field] for field in product_fields} for row in catalog
    ))
    write_csv(curated / "categorias.csv", ("categoria_id", "categoria"), (
        {"categoria_id": identifier, "categoria": label} for identifier, label in CATEGORIES
    ))
    write_csv(curated / "calendario.csv", ("data", "ano_mes", "ano"), (
        {"data": day, "ano_mes": day.strftime("%Y-%m"), "ano": day.year}
        for day in dates(START, last_day)
    ))
    write_csv(curated / "previsao.csv", forecast[0], forecast)
    write_csv(curated / "backtest.csv", backtest[0], backtest)
    write_preview(root / "docs" / "preview.svg", catalog, sales, forecast, backtest)
    return len(sales), len({row["pedido_id"] for row in sales}), len(forecast)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    args = parser.parse_args()
    lines, orders, forecasts = build(args.output_dir, args.seed)
    print(f"{lines:,} itens • {orders:,} pedidos • {forecasts} previsões por mês e categoria")


if __name__ == "__main__":
    main()
