"""Gera os arquivos versionáveis PBIP, PBIR e TMSL do relatório."""

import argparse
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
NAME = "BeautyCommerce"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/"
REPORT_SCHEMA = SCHEMA + "item/report/definition/"
RAW_URL = "memellsss/beauty-commerce-analytics/main/data/curated/"
INK, MUTED, PURPLE, PINK, CANVAS = "#252037", "#625A72", "#6335A5", "#A42C64", "#F7F3FA"
COUNT, CURRENCY = "#,0", '"R$ " #,0.00'
TYPES = {
    "string": "type text",
    "dateTime": "type date",
    "int64": "Int64.Type",
    "decimal": "Currency.Type",
}


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def stable_id(value):
    return uuid5(NAMESPACE_URL, "https://github.com/" + RAW_URL.split("/main/")[0] + "/" + value)


def measure(name, expression, description, fmt=None):
    item = {"name": name, "expression": expression, "description": description, "lineageTag": str(stable_id(name))}
    if fmt:
        item["formatString"] = fmt
    return item


def table(name, file, columns, measures=(), hidden=False):
    items = []
    for name_in_csv, label, datatype in columns:
        item = {
            "name": label,
            "dataType": datatype,
            "sourceColumn": name_in_csv,
            "summarizeBy": "none",
            "lineageTag": str(stable_id(f"{name}/{label}")),
        }
        if name_in_csv.endswith("_id"):
            item["isHidden"] = True
        if datatype == "dateTime":
            item["formatString"] = "dd/MM/yyyy"
            item["annotations"] = [{"name": "UnderlyingDateTimeDataType", "value": "Date"}]
        items.append(item)
    types = ", ".join(f'{{"{source}", {TYPES[datatype]}}}' for source, _, datatype in columns)
    return {
        "name": name,
        "isHidden": hidden,
        "lineageTag": str(stable_id(name)),
        "columns": items,
        "partitions": [{
            "name": name,
            "mode": "import",
            "source": {
                "type": "m",
                "expression": [
                    "let",
                    f'    Fonte = LerCsv("{file}.csv"),',
                    f'    Tipos = Table.TransformColumnTypes(Fonte, {{{types}}}, "en-US")',
                    "in",
                    "    Tipos",
                ],
            },
        }],
        **({"measures": list(measures)} if measures else {}),
    }


def relation(fact, key, dimension, dimension_key=None):
    return {
        "name": str(stable_id(f"{fact}/{key}/{dimension}")),
        "fromTable": fact,
        "fromColumn": key,
        "toTable": dimension,
        "toColumn": dimension_key or key,
        "crossFilteringBehavior": "oneDirection",
    }


def semantic_model():
    tables = [
        table("Calendário", "calendario", (
            ("data", "Data", "dateTime"), ("ano_mes", "Ano/mês", "string"), ("ano", "Ano", "int64"),
        )),
        table("Categorias", "categorias", (
            ("categoria_id", "ID da categoria", "string"), ("categoria", "Categoria", "string"),
        )),
        table("Produtos", "produtos", (
            ("produto_id", "ID do produto", "string"), ("produto", "Produto", "string"), ("marca", "Marca", "string"),
        )),
        table("Vendas", "vendas", (
            ("pedido_id", "ID do pedido", "string"), ("item", "Item", "int64"), ("data", "Data", "dateTime"),
            ("produto_id", "ID do produto", "string"), ("categoria_id", "ID da categoria", "string"),
            ("canal", "Canal", "string"), ("quantidade", "Quantidade", "int64"),
            ("preco_unitario", "Preço unitário", "decimal"), ("desconto_pct", "Desconto (%)", "int64"),
            ("receita_liquida", "Valor líquido", "decimal"),
        ), (
            measure("Receita líquida", "SUM('Vendas'[Valor líquido])", "Venda de produtos após descontos, sem frete ou impostos.", CURRENCY),
            measure("Pedidos", "DISTINCTCOUNT('Vendas'[ID do pedido])", "Pedidos distintos no contexto dos filtros.", COUNT),
            measure("Unidades vendidas", "SUM('Vendas'[Quantidade])", "Soma da quantidade vendida, não o número de linhas.", COUNT),
            measure("Ticket médio", "DIVIDE([Receita líquida], [Pedidos])", "Receita líquida por pedido distinto.", CURRENCY),
        )),
        table("Previsão", "previsao", (
            ("mes", "Mês", "dateTime"), ("categoria_id", "ID da categoria", "string"),
            ("unidades_previstas", "Quantidade", "int64"), ("metodo", "Método", "string"),
        ), (
            measure("Unidades previstas", "SUM('Previsão'[Quantidade])", "Previsão para janeiro a março de 2026.", COUNT),
            measure("Método escolhido", "SELECTEDVALUE('Previsão'[Método])", "Método selecionado por categoria no período de validação."),
        )),
        table("Backtest", "backtest", (
            ("mes", "Mês", "dateTime"), ("categoria_id", "ID da categoria", "string"),
            ("metodo", "Método", "string"), ("unidades_reais", "Unidades reais", "int64"),
            ("unidades_previstas", "Unidades previstas no teste", "int64"), ("erro_absoluto", "Erro absoluto", "int64"),
        ), (
            measure("WAPE no teste", "DIVIDE(SUM('Backtest'[Erro absoluto]), SUM('Backtest'[Unidades reais]))",
                    "Soma dos desvios absolutos por mês e categoria / total observado em out–dez/2025.", "0.0%"),
        )),
    ]
    return {
        "name": NAME,
        "compatibilityLevel": 1601,
        "model": {
            "culture": "pt-BR",
            "sourceQueryCulture": "pt-BR",
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "discourageImplicitMeasures": True,
            "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": False},
            "annotations": [
                {"name": "PBI_ProTooling", "value": '["DevMode"]'},
                {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
                {"name": "PBI_QueryOrder", "value": json.dumps(
                    ["PastaDados", "LerCsv"] + [entry["name"] for entry in tables], ensure_ascii=False
                )},
            ],
            "expressions": [
                {
                    "name": "PastaDados", "kind": "m", "lineageTag": str(stable_id("PastaDados")),
                    "expression": '"GitHub" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
                },
                {
                    "name": "LerCsv", "kind": "m", "lineageTag": str(stable_id("LerCsv")),
                    "expression": [
                        "(Nome as text) as table =>",
                        "let",
                        '    Conteudo = if PastaDados = "GitHub" then',
                        f'        Web.Contents("https://raw.githubusercontent.com", [RelativePath = "{RAW_URL}" & Nome])',
                        '        else File.Contents(PastaDados & "/" & Nome),',
                        '    Linhas = Csv.Document(Conteudo, [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
                        "    Cabecalhos = Table.PromoteHeaders(Linhas, [PromoteAllScalars = true])",
                        "in",
                        "    Cabecalhos",
                    ],
                },
            ],
            "tables": tables,
            "relationships": [
                relation("Vendas", "Data", "Calendário"),
                relation("Vendas", "ID do produto", "Produtos"),
                relation("Vendas", "ID da categoria", "Categorias"),
                relation("Previsão", "Mês", "Calendário", "Data"),
                relation("Previsão", "ID da categoria", "Categorias"),
                relation("Backtest", "Mês", "Calendário", "Data"),
                relation("Backtest", "ID da categoria", "Categorias"),
            ],
        },
    }


def literal(value):
    if isinstance(value, bool):
        token = str(value).lower()
    elif isinstance(value, (int, float)):
        token = f"{value}D"
    else:
        token = "'" + value.replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": token}}}


def color(value):
    return {"solid": {"color": literal(value)}}


def properties(**values):
    return [{"properties": values}]


def field(entity, name, kind="Column"):
    return {kind: {"Expression": {"SourceRef": {"Entity": entity}}, "Property": name}}


def textbox(*rows):
    paragraphs = [
        {"textRuns": [{
            "value": text,
            "textStyle": {"fontFamily": "Segoe UI", "fontSize": f"{size}pt", "color": shade,
                          "fontWeight": "bold" if bold else "normal"},
        }]} for text, size, shade, bold in rows
    ]
    return {"visualType": "textbox", "objects": {"general": properties(paragraphs=paragraphs)}}


def visual(kind, title=None, sort=None, **roles):
    query = {"queryState": {}}
    for role, fields in roles.items():
        projections = []
        for item in fields:
            value = next(iter(item.values()))
            name, entity = value["Property"], value["Expression"]["SourceRef"]["Entity"]
            projections.append({
                "field": item, "queryRef": f"{entity}.{name}", "nativeQueryRef": name,
                **({"active": True} if role in ("Category", "Values") and "Column" in item else {}),
            })
        query["queryState"][role] = {"projections": projections}
    if sort:
        query["sortDefinition"] = {"sort": [{"field": sort[0], "direction": sort[1]}], "isDefaultSort": False}
    formatting = {
        "background": properties(show=literal(True), color=color("#FFFFFF"), transparency=literal(0)),
    }
    if title:
        formatting["title"] = properties(
            show=literal(True), text=literal(title), fontSize=literal(13), fontColor=color(INK), titleWrap=literal(True)
        )
    result = {"visualType": kind, "query": query, "visualContainerObjects": formatting, "drillFilterOtherVisuals": True}
    if kind == "slicer":
        result["objects"] = {"data": properties(mode=literal("Dropdown"))}
    return result


def write_page(directory, page_id, label, height, visuals):
    write_json(directory / page_id / "page.json", {
        "$schema": REPORT_SCHEMA + "page/1.4.0/schema.json",
        "name": page_id, "displayName": label, "displayOption": "FitToPage", "width": 1280, "height": height,
        "objects": {"background": properties(color=color(CANVAS), transparency=literal(0))},
    })
    for i, (key, x, y, w, h, config) in enumerate(visuals, 1):
        visual_id = stable_id(f"{page_id}/{key}").hex[:20]
        write_json(directory / page_id / "visuals" / visual_id / "visual.json", {
            "$schema": REPORT_SCHEMA + "visualContainer/2.7.0/schema.json",
            "name": visual_id,
            "position": {"x": x, "y": y, "z": i * 1000, "width": w, "height": h, "tabOrder": i * 1000},
            "visual": config,
        })


def report_pages(directory):
    revenue = field("Vendas", "Receita líquida", "Measure")
    orders = field("Vendas", "Pedidos", "Measure")
    units = field("Vendas", "Unidades vendidas", "Measure")
    ticket = field("Vendas", "Ticket médio", "Measure")
    forecast = field("Previsão", "Unidades previstas", "Measure")
    wape = field("Backtest", "WAPE no teste", "Measure")
    method = field("Previsão", "Método escolhido", "Measure")
    month = field("Calendário", "Ano/mês")
    category = field("Categorias", "Categoria")
    brand = field("Produtos", "Marca")
    product = field("Produtos", "Produto")
    channel = field("Vendas", "Canal")
    overview = stable_id("overview").hex[:20]
    demand = stable_id("demand").hex[:20]
    write_json(directory / "pages.json", {
        "$schema": REPORT_SCHEMA + "pagesMetadata/1.0.0/schema.json",
        "pageOrder": [overview, demand], "activePageName": overview,
    })
    write_page(directory, overview, "Visão de vendas", 880, [
        ("header", 24, 20, 760, 94, textbox(
            ("BEAUTY COMMERCE   /   01", 11, PURPLE, True),
            ("Performance de e-commerce", 24, INK, True),
            ("Dados sintéticos · jan/2024 a dez/2025", 11, MUTED, False),
        )),
        ("channel", 804, 35, 214, 73, visual("slicer", "Canal", Values=[channel])),
        ("category", 1032, 35, 224, 73, visual("slicer", "Categoria", Values=[category])),
        *((f"kpi{i}", 24 + 311 * i, 122, 299, 107, visual("cardVisual", Data=[metric]))
          for i, metric in enumerate((revenue, orders, units, ticket))),
        ("trend", 24, 245, 758, 262, visual(
            "lineChart", "Receita líquida por mês", (month, "Ascending"), Category=[month], Y=[revenue]
        )),
        ("brands", 798, 245, 458, 262, visual(
            "clusteredBarChart", "Ranking de marcas por receita", (revenue, "Descending"), Category=[brand], Y=[revenue]
        )),
        ("products", 24, 523, 758, 326, visual(
            "tableEx", "Desempenho por produto", (revenue, "Descending"), Values=[product, brand, units, revenue]
        )),
        ("categories", 798, 523, 458, 326, visual(
            "clusteredBarChart", "Unidades por categoria", (units, "Descending"), Category=[category], Y=[units]
        )),
    ])
    write_page(directory, demand, "Previsão de demanda", 860, [
        ("header", 24, 20, 940, 94, textbox(
            ("BEAUTY COMMERCE   /   02", 11, PURPLE, True),
            ("Previsão de demanda", 24, INK, True),
            ("Histórico até dez/2025 · projeção: jan–mar/2026", 11, MUTED, False),
        )),
        ("category", 1024, 35, 232, 73, visual("slicer", "Categoria", Values=[category])),
        ("forecast", 24, 122, 608, 103, visual("cardVisual", Data=[forecast])),
        ("wape", 648, 122, 608, 103, visual("cardVisual", Data=[wape])),
        ("trend", 24, 241, 1232, 308, visual(
            "lineChart", "Unidades vendidas e previstas por mês", (month, "Ascending"), Category=[month], Y=[units, forecast]
        )),
        ("methods", 24, 565, 790, 270, visual(
            "tableEx", "Previsão e erro por categoria", (forecast, "Descending"), Values=[category, forecast, method, wape]
        )),
        ("notes", 830, 570, 426, 253, textbox(
            ("COMO LER A PREVISÃO", 12, PURPLE, True),
            ("O método foi escolhido em jul–set/2025 e testado em out–dez/2025.", 12, INK, False),
            ("WAPE: soma dos erros absolutos por mês e categoria dividida pelo total de unidades observadas no teste.", 12, INK, False),
            ("Cenário simulado; não indica demanda de mercado.", 11, MUTED, False),
        )),
    ])


def build(root):
    folder = root / "powerbi"
    report = folder / (NAME + ".Report")
    model = folder / (NAME + ".SemanticModel")
    write_json(folder / (NAME + ".pbip"), {
        "$schema": SCHEMA + "pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": report.name}}], "settings": {"enableAutoRecovery": True},
    })
    write_json(report / "definition.pbir", {
        "$schema": SCHEMA + "item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": "../" + model.name}},
    })
    write_json(model / "definition.pbism", {
        "$schema": SCHEMA + "item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "1.0", "settings": {"qnaEnabled": False},
    })
    write_json(model / "model.bim", semantic_model())
    theme = "BeautyCommerceTheme.json"
    write_json(report / "StaticResources" / "RegisteredResources" / theme, {
        "name": "Beauty Commerce", "dataColors": [PURPLE, PINK, "#137F7A", "#DE9D31", "#583E72"],
        "background": "#FFFFFF", "foreground": INK, "tableAccent": PURPLE,
    })
    write_json(report / "definition" / "report.json", {
        "$schema": REPORT_SCHEMA + "report/3.0.0/schema.json",
        "themeCollection": {"customTheme": {
            "name": theme, "type": "RegisteredResources",
            "reportVersionAtImport": {"visual": "1.8.100", "report": "2.0.100", "page": "1.3.100"},
        }},
        "resourcePackages": [{
            "name": "RegisteredResources", "type": "RegisteredResources",
            "items": [{"name": theme, "path": theme, "type": "CustomTheme"}],
        }],
        "settings": {"useEnhancedTooltips": True, "defaultFilterActionIsDataFilter": True},
    })
    write_json(report / "definition" / "version.json", {
        "$schema": REPORT_SCHEMA + "versionMetadata/1.0.0/schema.json", "version": "2.0.0",
    })
    report_pages(report / "definition" / "pages")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    build(parser.parse_args().output_dir)
