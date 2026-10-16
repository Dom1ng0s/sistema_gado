#!/usr/bin/env bash
# Re-baixa os arquivos de fonte servidos localmente (static/fonts/).
# Rodar quando quiser atualizar a versão do Google Fonts. Depois, conferir
# se os unicode-range em static/css/fonts.css ainda batem com o CSS de origem.
#
# Archivo cobre todo o texto da interface; IBM Plex Mono cobre todo número.
# A separação é proposital: a tarefa do sistema é comparar colunas de números,
# e só uma monoespaçada alinha dígito com dígito sem depender de tabular-nums.
set -euo pipefail

DEST="$(cd "$(dirname "${BASH_SOURCE[0]}")/../static/fonts" && pwd)"
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
CSS_URL='https://fonts.googleapis.com/css2?family=Archivo:wght@400..700&family=IBM+Plex+Mono:wght@400;500&display=swap'

echo "CSS de origem (confira os unicode-range se algo mudou):"
echo "  $CSS_URL"
echo

# Archivo é fonte variável: um arquivo por subset cobre 400–700.
# IBM Plex Mono é estática, então são dois pesos por subset.
declare -A FILES=(
  [archivo-latin.woff2]='https://fonts.gstatic.com/s/archivo/v25/k3kPo8UDI-1M0wlSV9XAw6lQkqWY8Q82sLydOxI.woff2'
  [archivo-latin-ext.woff2]='https://fonts.gstatic.com/s/archivo/v25/k3kPo8UDI-1M0wlSV9XAw6lQkqWY8Q82sLyTOxK-vA.woff2'
  [plex-mono-400-latin.woff2]='https://fonts.gstatic.com/s/ibmplexmono/v20/-F63fjptAgt5VM-kVkqdyU8n1i8q1w.woff2'
  [plex-mono-400-latin-ext.woff2]='https://fonts.gstatic.com/s/ibmplexmono/v20/-F63fjptAgt5VM-kVkqdyU8n1iEq129k.woff2'
  [plex-mono-500-latin.woff2]='https://fonts.gstatic.com/s/ibmplexmono/v20/-F6qfjptAgt5VM-kVkqdyU8n3twJwlBFgg.woff2'
  [plex-mono-500-latin-ext.woff2]='https://fonts.gstatic.com/s/ibmplexmono/v20/-F6qfjptAgt5VM-kVkqdyU8n3twJwl5FgtIU.woff2'
)

for name in "${!FILES[@]}"; do
  echo "→ $name"
  curl -sfL -A "$UA" -o "$DEST/$name" "${FILES[$name]}"
done

echo
echo "OK — $(ls -1 "$DEST"/*.woff2 | wc -l) arquivos em $DEST"
