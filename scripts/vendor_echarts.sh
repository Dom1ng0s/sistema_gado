#!/usr/bin/env bash
# Re-baixa o bundle do ECharts servido localmente (static/vendor/).
# Rodar para atualizar a versão. Depois:
#   1. conferir se os <script src="vendor/echarts-<versao>..."> nos templates
#      (templates/*.html) e em static/components.html apontam para o arquivo novo;
#   2. remover o arquivo da versao antiga;
#   3. atualizar VERSION aqui e a secao 5.3 do DOCUMENTATION.md.
#
# Bundle "simple": Line + Bar + Pie + Scatter + Canvas + componentes basicos
# (title/tooltip/legend/grid/markLine). Cobre todos os graficos do app e pesa
# ~45% do bundle completo. Se algum grafico novo precisar de outro tipo de serie
# (heatmap, radar, candlestick...), trocar para echarts.min.js completo.
set -euo pipefail

VERSION='5.6.0'
DEST="$(cd "$(dirname "${BASH_SOURCE[0]}")/../static/vendor" && pwd)"
FILE="echarts-${VERSION}.simple.min.js"
URL="https://cdn.jsdelivr.net/npm/echarts@${VERSION}/dist/echarts.simple.min.js"

echo "→ $FILE"
echo "  $URL"
curl -sfL -o "$DEST/$FILE" "$URL"

echo
echo "OK — $(wc -c < "$DEST/$FILE") bytes em $DEST/$FILE"
echo "sha256: $(sha256sum "$DEST/$FILE" | cut -d' ' -f1)"
