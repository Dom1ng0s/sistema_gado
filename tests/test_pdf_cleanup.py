"""Issue #37 — limpeza oportunística de PDFs órfãos em /tmp."""
import os
import time

from routes.api import _limpar_pdfs_orfaos, _PDF_DIR, _PDF_MAX_AGE


def _touch(nome, idade_seg):
    caminho = os.path.join(_PDF_DIR, nome)
    open(caminho, 'w').close()
    t = time.time() - idade_seg
    os.utime(caminho, (t, t))
    return caminho


def test_limpa_orfaos_antigos_preserva_recentes_e_alheios():
    velho   = _touch('sgg_pdf_teste_velho.pending', _PDF_MAX_AGE + 120)
    novo    = _touch('sgg_pdf_teste_novo.pending', 10)
    alheio  = _touch('outro_arquivo_qualquer.tmp', _PDF_MAX_AGE + 120)
    try:
        _limpar_pdfs_orfaos()
        assert not os.path.exists(velho)      # órfão antigo removido
        assert os.path.exists(novo)           # job recente intacto
        assert os.path.exists(alheio)         # não toca em arquivos de terceiros
    finally:
        for p in (velho, novo, alheio):
            if os.path.exists(p):
                os.remove(p)
