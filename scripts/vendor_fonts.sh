#!/usr/bin/env bash
# Re-baixa os arquivos de fonte servidos localmente (static/fonts/).
# Rodar quando quiser atualizar a versão do Google Fonts. Depois, conferir
# se os unicode-range em static/css/fonts.css ainda batem com o CSS de origem.
set -euo pipefail

DEST="$(cd "$(dirname "${BASH_SOURCE[0]}")/../static/fonts" && pwd)"
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
CSS_URL='https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600&family=Rubik:wght@400;500;600&display=swap'

echo "CSS de origem (confira os unicode-range se algo mudou):"
echo "  $CSS_URL"
echo

declare -A FILES=(
  [playfairdisplay-latin.woff2]='https://fonts.gstatic.com/s/playfairdisplay/v40/nuFiD-vYSZviVYUb_rj3ij__anPXDTzYgA.woff2'
  [playfairdisplay-latin-ext.woff2]='https://fonts.gstatic.com/s/playfairdisplay/v40/nuFiD-vYSZviVYUb_rj3ij__anPXDTLYgFE_.woff2'
  [rubik-latin.woff2]='https://fonts.gstatic.com/s/rubik/v31/iJWKBXyIfDnIV7nBrXw.woff2'
  [rubik-latin-ext.woff2]='https://fonts.gstatic.com/s/rubik/v31/iJWKBXyIfDnIV7nPrXyi0A.woff2'
)

for name in "${!FILES[@]}"; do
  echo "→ $name"
  curl -sfL -A "$UA" -o "$DEST/$name" "${FILES[$name]}"
done

echo
echo "OK — $(ls -1 "$DEST"/*.woff2 | wc -l) arquivos em $DEST"
