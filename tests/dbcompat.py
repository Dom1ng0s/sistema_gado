"""Ponte de compatibilidade para os testes que abrem conexão própria ao banco.

Antes do #115 os testes usavam ``mysql.connector.connect(**DB_CONFIG)`` e
``cursor.lastrowid``. Com o Postgres (psycopg 3) não existe ``lastrowid``; este
cursor recupera o id do último INSERT via ``lastval()`` (a sequência por trás de
``GENERATED AS IDENTITY``), preservando o padrão dos helpers de teste.
"""
import psycopg

from conftest import TEST_DB_CONFIG


class _LastrowidCursor(psycopg.Cursor):
    @property
    def lastrowid(self):
        # Os helpers de teste chamam `cur.lastrowid` logo após um INSERT e não
        # leem mais resultados desse cursor — seguro rodar lastval() aqui.
        try:
            super().execute("SELECT lastval()")
            row = super().fetchone()
            return row[0] if row else None
        except psycopg.Error:
            return None


def connect(**overrides):
    cfg = {**TEST_DB_CONFIG, **overrides}
    return psycopg.connect(cursor_factory=_LastrowidCursor, **cfg)
