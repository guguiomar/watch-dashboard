# Relógios · custo desembarcado na UE

Ferramenta pessoal, em português de Portugal, para comparar o retalho, o mercado secundário e um exemplo de custo de importar relógios de Rolex, Omega, Cartier e Panerai para Portugal.

**Não é aconselhamento financeiro.** Os números foram lidos à mão em páginas públicas e podem ficar desactualizados.

## Onde está o quê

- `data/watches.json` — as referências, preços, fontes e a leitura de cada modelo
- `data/indices.json` — os poucos pontos de índices de mercado que são públicos (sem séries inventadas)
- `index.html`, `css/style.css`, `js/app.js` — o site estático

## Como actualizar

Uma vez por mês:

1. Rever os preços oficiais ou de retalhista em Portugal e as páginas WatchCharts ligadas em cada modelo.
2. Actualizar o câmbio do BCE em `data/watches.json` (`fx.usd_per_eur`).
3. Recalcular `market_eur`, `dealer_eur`, `landed_eur` e `premium_vs_pt` com a fórmula:

   `desembarcado = 1,23 × (mercado em EUR + 150 € + 0,80 €)`

   Os 150 € de portes são uma estimativa. O direito usa o tecto de 0,80 € do tarifário da UE para relógios de pulso de aço (SH 9102).
4. Não recolher a Chrono24 de forma automatizada.

## Publicação

Site estático, servido pelo GitHub Pages a partir do ramo `main`.
