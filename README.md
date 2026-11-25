# Beauty Commerce Analytics

Projeto de portfólio em **Python e Power BI** sobre o desempenho de um e-commerce fictício de produtos de beleza. O relatório responde a três perguntas: **quando a receita aumenta, quais marcas e produtos se destacam e quantas unidades esperar por categoria no próximo trimestre?**

![Prévia da análise: receita, pedidos, unidades, ticket médio, ranking de marcas e previsão de demanda](docs/preview.svg)

_Prévia estática gerada em Python com os mesmos dados do relatório. Não é uma captura do Power BI._

## O que os dados mostram

- **R$ 326.870,20** em receita líquida simulada, **3.334 pedidos** e **5.440 unidades** entre jan/2024 e dez/2025.
- **Nov/2025** teve a maior receita mensal do cenário (R$ 21.767,25). A simulação aumenta o volume em novembro; isso não demonstra uma tendência de mercado.
- **Estúdio Aurora** liderou em receita (R$ 98.887,40); **Protetor facial** foi o produto mais vendido em volume (410 unidades).
- A projeção de **jan–mar/2026** soma **794 unidades**. O **WAPE foi de 14,0%** no trimestre de teste, somando erros absolutos por mês e categoria antes de dividir pelo total observado.

Todos os pedidos, marcas e valores pertencem a um cenário simulado. O projeto não usa dados do estágio, de clientes, de redes sociais ou de vendas reais. Aqui, o ranking é por **receita de vendas**, não por menções a marcas.

## Abrir no Power BI

1. Clone ou baixe o repositório inteiro, mantendo as pastas juntas. No Windows, abra [`powerbi/BeautyCommerce.pbip`](powerbi/BeautyCommerce.pbip) no **Power BI Desktop** atualizado. Se sua versão exigir, habilite **Projeto do Power BI (.pbip)** e **formato de relatório aprimorado (PBIR)** em **Arquivo → Opções e configurações → Opções → Recursos de visualização** e reinicie.
2. Clique em **Atualizar** para carregar os CSVs públicos deste repositório. Se o Power BI pedir credenciais para `https://raw.githubusercontent.com`, selecione **Anônimo**.
3. Use **Visão de vendas** para filtrar por canal e categoria, ver os KPIs, o ranking e o desempenho por produto. Em **Previsão de demanda**, filtre por categoria e compare as unidades observadas com a projeção. A tabela dessa página mostra o método escolhido e o WAPE de teste por categoria.

**Para trabalhar offline ou trocar a semente da simulação:** em **Transformar dados → Editar parâmetros**, altere `PastaDados` de `GitHub` para o caminho absoluto da pasta `data/curated` do clone. Depois aplique as alterações e atualize. O projeto usa `.pbip` / PBIR e `model.bim` para que o layout, as medidas DAX e as consultas M possam ser versionados; o cache local não é publicado.

## Rodar o pipeline

Requer **Python 3.12+**. Não é necessário instalar pacotes.

```bash
python -m src.pipeline
python -m unittest discover -s tests -v
```

O pipeline recria os CSVs brutos em `data/raw/` (não versionados), valida chaves e valores e grava as tabelas tratadas em `data/curated/`. A semente padrão é `42`. Para testar outro cenário sem substituir os arquivos do repositório:

```bash
python -m src.pipeline --seed 123 --output-dir ./experimento
```

O projeto Power BI já vem no repositório. Se quiser regenerar a definição de referência a partir do código, use `python tools/build_powerbi.py`. Essa execução reescreve as definições geradas; edições manuais feitas no Desktop não voltam automaticamente para o gerador.

## Modelo e métricas

| Tabelas | Granularidade |
| --- | --- |
| `vendas.csv` | Um item por pedido; um pedido pode ter vários itens. |
| `produtos.csv`, `categorias.csv`, `calendario.csv` | Um produto, uma categoria e um dia por linha, respectivamente. |
| `previsao.csv` | Uma previsão por mês e categoria (jan–mar/2026). |
| `backtest.csv` | Demanda observada, estimada e erro absoluto por mês e categoria (out–dez/2025). |

Receita líquida = quantidade × preço unitário × (1 − desconto), sem frete ou impostos. Ticket médio = receita líquida ÷ pedidos distintos. A categoria e o calendário filtram vendas, previsão e backtest; a previsão não tem granularidade de produto, marca ou canal.

### Como a previsão foi testada

1. O pipeline agrega **unidades**, não receita, por mês e categoria.
2. Com jan/2024–jun/2025 como histórico, compara a média fixa dos últimos três meses com um método sazonal: usa o mesmo mês do ano anterior, ajustado pela razão entre o trimestre mais recente e o equivalente do ano anterior. O menor erro absoluto acumulado em **jul–set/2025** define o método de cada categoria.
3. O método escolhido é então avaliado em **out–dez/2025**, usando apenas o histórico disponível até setembro. Separar os períodos evita escolher o método em cima do mesmo trimestre usado para apresentar o erro.
4. Por fim, o método é reaplicado com o histórico completo até dez/2025 para estimar **jan–mar/2026**.

São métodos de referência sobre apenas dois anos simulados. A projeção não inclui intervalos de confiança e não deve orientar compras ou decisões comerciais reais.
