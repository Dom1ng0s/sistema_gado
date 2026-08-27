#!/usr/bin/env bash
# Re-baixa os arquivos de fonte servidos localmente (static/fonts/).
# Rodar quando quiser atualizar a versão do Google Fonts. Depois, conferir
# se os unicode-range em static/css/fonts.css ainda batem com o CSS de origem.
set -euo pipefail

DEST="$(cd "$(dirname "${BASH_SOURCE[0]}")/../static/fonts" && pwd)"
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
CSS_URL='https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&display=swap'

echo "CSS de origem (confira os unicode-range se algo mudou):"
echo "  $CSS_URL"
echo

declare -A FILES=(
  [fraunces-latin.woff2]='https://fonts.gstatic.com/s/fraunces/v38/6NU78FyLNQOQZAnv9bYEvDiIdE9Ea92uemAk_WBq8U_9v0c2Wa0KxC9TeA.woff2'
  [fraunces-latin-ext.woff2]='https://fonts.gstatic.com/s/fraunces/v38/6NU78FyLNQOQZAnv9bYEvDiIdE9Ea92uemAk_WBq8U_9v0c2Wa0KxCFTeO-U.woff2'
  [inter-latin.woff2]='https://fonts.gstatic.com/s/inter/v20/UcC73FwrK3iLTeHuS_nVMrMxCp50SjIa1ZL7.woff2'
  [inter-latin-ext.woff2]='https://fonts.gstatic.com/s/inter/v20/UcC73FwrK3iLTeHuS_nVMrMxCp50SjIa25L7SUc.woff2'
)

for name in "${!FILES[@]}"; do
  echo "→ $name"
  curl -sfL -A "$UA" -o "$DEST/$name" "${FILES[$name]}"
done

echo
echo "OK — $(ls -1 "$DEST"/*.woff2 | wc -l) arquivos em $DEST"
