import csv
import json
import re
import unittest
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

from src.pipeline import CATEGORIES, END, ROOT, build, clean_sales, forecast_demand, forecast_values, read_csv, write_csv
from tools.build_powerbi import NAME, build as build_powerbi


class ProjectTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = TemporaryDirectory()
        cls.addClassCleanup(cls.scratch.cleanup)
        cls.root = Path(cls.scratch.name)
        build(cls.root)
        build_powerbi(cls.root)
        cls.curated = cls.root / "data" / "curated"
        cls.sales = read_csv(cls.curated / "vendas.csv")
        cls.forecast = read_csv(cls.curated / "previsao.csv")
        cls.backtest = read_csv(cls.curated / "backtest.csv")
        cls.powerbi = cls.root / "powerbi"
        cls.model = read_json(cls.powerbi / (NAME + ".SemanticModel") / "model.bim")["model"]

    def test_versioned_artifacts_are_reproducible(self):
        def published_files(root):
            return sorted(
                p.relative_to(root) for folder in ("data/curated", "powerbi", "docs") for p in (root / folder).rglob("*")
                if p.is_file() and ".pbi" not in p.parts and (
                    folder != "docs" or p.name == "preview.svg"
                )
            )

        expected = published_files(self.root)
        self.assertEqual(expected, published_files(ROOT))
        for p in expected:
            with self.subTest(path=p):
                self.assertEqual((self.root / p).read_bytes(), (ROOT / p).read_bytes())

    def test_sales_grain_and_amounts(self):
        keys = {(r["pedido_id"], r["item"]) for r in self.sales}
        self.assertEqual(len(self.sales), len(keys))
        self.assertGreater(len(self.sales), len({r["pedido_id"] for r in self.sales}))
        for r in self.sales:
            expected = Decimal(r["preco_unitario"]) * int(r["quantidade"]) * (100 - int(r["desconto_pct"])) / 100
            self.assertEqual(Decimal(r["receita_liquida"]), expected.quantize(Decimal("0.01")))
            self.assertGreater(int(r["quantidade"]), 0)

    def test_etl_rejects_invalid_product(self):
        with TemporaryDirectory() as temporary_directory:
            bad = Path(temporary_directory)
            source = self.root / "data" / "raw"
            (bad / "catalogo.csv").write_bytes((source / "catalogo.csv").read_bytes())
            orders = read_csv(source / "pedidos.csv")
            orders[0]["produto_id"] = "unknown"
            write_csv(bad / "pedidos.csv", orders[0], orders)
            with self.assertRaisesRegex(ValueError, "Produto desconhecido"):
                clean_sales(bad)

    def test_forecast_baselines(self):
        self.assertEqual(forecast_values([1, 2, 30, 60, 90], "Media 3 meses", 3), [60, 60, 60])
        self.assertEqual(forecast_values([100] * 12 + [130] * 3, "Sazonal", 3), [130] * 3)
        self.assertEqual(forecast_values([0] * 3 + [70] * 9 + [420] * 3, "Sazonal", 3), [70] * 3)
        with self.assertRaises(ValueError):
            forecast_values([1, 2, 3], "Sazonal", 3)

    def test_forecast_and_backtest_have_expected_months_and_grain(self):
        categories = {identifier for identifier, _ in CATEGORIES}
        for rows, months in (
            (self.forecast, ("2026-01-01", "2026-02-01", "2026-03-01")),
            (self.backtest, ("2025-10-01", "2025-11-01", "2025-12-01")),
        ):
            self.assertEqual(len(rows), len(categories) * len(months))
            self.assertEqual({(r["categoria_id"], r["mes"]) for r in rows}, {(c, m) for c in categories for m in months})
            self.assertTrue(all(int(r["unidades_previstas"]) >= 0 for r in rows))
        self.assertTrue(all(date.fromisoformat(r["mes"]) > END for r in self.forecast))
        actuals = Counter()
        for row in self.sales:
            actuals[row["categoria_id"], row["data"][:7]] += int(row["quantidade"])
        for r in self.backtest:
            self.assertEqual(int(r["unidades_reais"]), actuals[r["categoria_id"], r["mes"][:7]])
            self.assertEqual(int(r["erro_absoluto"]), abs(int(r["unidades_reais"]) - int(r["unidades_previstas"])))

    def test_holdout_does_not_influence_its_own_predictions(self):
        _, sales = clean_sales(self.root / "data" / "raw")
        _, baseline = forecast_demand(sales)
        revised = [
            {**row, "quantidade": row["quantidade"] * 8} if row["data"] >= date(2025, 10, 1) else row
            for row in sales
        ]
        _, changed = forecast_demand(revised)
        def selection(rows):
            return [(r["mes"], r["categoria_id"], r["metodo"], r["unidades_previstas"]) for r in rows]

        self.assertEqual(selection(baseline), selection(changed))
        self.assertNotEqual(baseline[0]["unidades_reais"], changed[0]["unidades_reais"])

    def test_model_csv_contract_and_relationships(self):
        sources = {}
        columns = {}
        for table in self.model["tables"]:
            name = table["name"]
            columns[name] = {c["name"]: c["sourceColumn"] for c in table["columns"]}
            partition = "\n".join(table["partitions"][0]["source"]["expression"])
            filename = re.search(r'LerCsv\("([^"]+)"\)', partition)[1]
            with (self.curated / filename).open(encoding="utf-8", newline="") as file:
                reader = csv.DictReader(file)
                self.assertEqual(set(reader.fieldnames), set(columns[name].values()))
                sources[name] = list(reader)
        for relation in self.model["relationships"]:
            a, b = relation["fromTable"], relation["toTable"]
            left = [r[columns[a][relation["fromColumn"]]] for r in sources[a]]
            right = [r[columns[b][relation["toColumn"]]] for r in sources[b]]
            self.assertEqual(len(right), len(set(right)))
            self.assertTrue(set(left) <= set(right), relation)
        dates = [date.fromisoformat(r["data"]) for r in sources["Calendário"]]
        self.assertEqual(len(dates), (dates[-1] - dates[0]).days + 1)
        self.assertEqual(dates[-1], date(2026, 3, 31))

    def test_report_folders_visual_fields_and_positions(self):
        shortcut = read_json(self.powerbi / (NAME + ".pbip"))
        report = self.powerbi / shortcut["artifacts"][0]["report"]["path"]
        reference = read_json(report / "definition.pbir")
        self.assertTrue((report / reference["datasetReference"]["byPath"]["path"] / "model.bim").is_file())
        pages = report / "definition" / "pages"
        meta = read_json(pages / "pages.json")
        self.assertEqual(len(meta["pageOrder"]), 2)
        self.assertIn(meta["activePageName"], meta["pageOrder"])
        fields = {
            (table["name"], kind): {item["name"] for item in table.get(key, [])}
            for table in self.model["tables"]
            for kind, key in (("Measure", "measures"), ("Column", "columns"))
        }
        for page_id in meta["pageOrder"]:
            page = read_json(pages / page_id / "page.json")
            self.assertEqual(page["name"], page_id)
            visuals = list((pages / page_id / "visuals").glob("*/visual.json"))
            self.assertGreaterEqual(len(visuals), 7)
            for path in visuals:
                entry = read_json(path)
                self.assertEqual(entry["name"], path.parent.name)
                pos = entry["position"]
                self.assertLessEqual(pos["x"] + pos["width"], page["width"])
                self.assertLessEqual(pos["y"] + pos["height"], page["height"])
                for state in entry["visual"].get("query", {}).get("queryState", {}).values():
                    for projection in state["projections"]:
                        kind, item = next(iter(projection["field"].items()))
                        entity = item["Expression"]["SourceRef"]["Entity"]
                        self.assertIn(item["Property"], fields[entity, kind])

    def test_svg_preview_is_valid_xml(self):
        svg = ElementTree.parse(self.root / "docs" / "preview.svg")
        self.assertEqual(svg.getroot().tag, "{http://www.w3.org/2000/svg}svg")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))
