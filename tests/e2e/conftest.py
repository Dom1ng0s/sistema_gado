"""
Fixtures for E2E tests with Playwright.

Requires:
  - Local MySQL accessible at localhost:3306 with user gado_test/gado123
  - GRANT ALL PRIVILEGES ON sistema_gado_e2e.* TO 'gado_test'@'localhost';
  - playwright browsers installed: playwright install chromium

Run all E2E tests:
  pytest tests/e2e/ -v

Run one file:
  pytest tests/e2e/test_login.py -v
"""

import os
import socket
import subprocess
import time

import mysql.connector
import pytest
from playwright.sync_api import sync_playwright
from werkzeug.security import generate_password_hash

E2E_PORT = 5099
E2E_DB_NAME = "sistema_gado_e2e"
E2E_DB_HOST = os.getenv("TEST_DB_HOST", "localhost")
E2E_DB_USER = os.getenv("TEST_DB_USER", "gado_test")
E2E_DB_PASS = os.getenv("TEST_DB_PASSWORD", "gado123")
E2E_DB_PORT = int(os.getenv("TEST_DB_PORT", "3306"))

E2E_USER = "e2euser"
E2E_PASS = "e2e_password123"

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except (OSError, ConnectionRefusedError):
            time.sleep(0.3)
    return False


@pytest.fixture(scope="session")
def e2e_db():
    """Creates the E2E test database, seeds it, and tears it down after the session."""
    base_cfg = {
        "host": E2E_DB_HOST,
        "user": E2E_DB_USER,
        "password": E2E_DB_PASS,
        "port": E2E_DB_PORT,
    }
    conn = mysql.connector.connect(**base_cfg)
    cursor = conn.cursor()

    try:
        cursor.execute(f"DROP DATABASE IF EXISTS {E2E_DB_NAME}")
        cursor.execute(f"CREATE DATABASE {E2E_DB_NAME}")
        cursor.execute(f"USE {E2E_DB_NAME}")

        cursor.execute("""
        CREATE TABLE usuarios (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            email VARCHAR(255) NULL UNIQUE
        )""")

        cursor.execute("""
        CREATE TABLE configuracoes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL UNIQUE,
            nome_fazenda VARCHAR(100),
            cidade_estado VARCHAR(100),
            area_total DECIMAL(10, 2),
            FOREIGN KEY (user_id) REFERENCES usuarios(id)
        )""")

        cursor.execute("""
        CREATE TABLE lotes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            codigo_lote VARCHAR(50) NOT NULL,
            descricao TEXT,
            data_aquisicao DATE,
            deleted_at DATETIME NULL DEFAULT NULL,
            FOREIGN KEY (user_id) REFERENCES usuarios(id)
        )""")

        cursor.execute("""
        CREATE TABLE animais (
            id INT AUTO_INCREMENT PRIMARY KEY,
            brinco VARCHAR(50) NOT NULL,
            sexo CHAR(1) NOT NULL,
            raca VARCHAR(100) NULL,
            data_compra DATE NOT NULL,
            data_nascimento DATE NULL,
            preco_compra DECIMAL(10, 2),
            data_venda DATE,
            preco_venda DECIMAL(10, 2),
            user_id INT NOT NULL,
            lote_id INT,
            deleted_at DATETIME,
            pai_id INT NULL,
            mae_id INT NULL,
            FOREIGN KEY (user_id) REFERENCES usuarios(id),
            FOREIGN KEY (pai_id) REFERENCES animais(id) ON DELETE SET NULL,
            FOREIGN KEY (mae_id) REFERENCES animais(id) ON DELETE SET NULL
        )""")

        cursor.execute("""
        CREATE TABLE pesagens (
            id INT AUTO_INCREMENT PRIMARY KEY,
            animal_id INT NOT NULL,
            data_pesagem DATE NOT NULL,
            peso DECIMAL(10, 2) NOT NULL,
            deleted_at DATETIME,
            FOREIGN KEY (animal_id) REFERENCES animais(id)
        )""")

        # Needed by /painel (get_vencendo_em_dias)
        cursor.execute("""
        CREATE TABLE protocolos_sanitarios (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            nome VARCHAR(200) NOT NULL,
            descricao TEXT,
            intervalo_dias INT NOT NULL,
            proxima_aplicacao DATE NOT NULL,
            ativo TINYINT(1) DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )""")

        # Seed: test user
        pw_hash = generate_password_hash(E2E_PASS)
        cursor.execute(
            "INSERT INTO usuarios (username, password_hash, email) VALUES (%s, %s, %s)",
            (E2E_USER, pw_hash, "e2euser@test.local"),
        )
        user_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO configuracoes (user_id, nome_fazenda) VALUES (%s, %s)",
            (user_id, "Fazenda E2E"),
        )

        # Seed: lote + 3 animals for the pesagem test
        cursor.execute(
            "INSERT INTO lotes (user_id, codigo_lote, descricao, data_aquisicao) VALUES (%s, %s, %s, %s)",
            (user_id, "LOTE-E2E-BASE", "Lote pré-existente para testes de pesagem", "2024-01-15"),
        )
        lote_id = cursor.lastrowid

        animal_ids = []
        for i in range(1, 4):
            cursor.execute(
                "INSERT INTO animais (brinco, sexo, raca, data_compra, preco_compra, user_id, lote_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (f"BASE-{i:03d}", "M", "Nelore", "2024-01-15", 1800.00, user_id, lote_id),
            )
            animal_ids.append(cursor.lastrowid)

        conn.commit()

        yield {"user_id": user_id, "lote_id": lote_id, "animal_ids": animal_ids}

    finally:
        cursor.close()
        conn.close()
        # Cleanup: drop the E2E database
        cleanup = mysql.connector.connect(**base_cfg)
        c = cleanup.cursor()
        c.execute(f"DROP DATABASE IF EXISTS {E2E_DB_NAME}")
        cleanup.commit()
        cleanup.close()


@pytest.fixture(scope="session")
def live_server(e2e_db):
    """Starts the Flask app as a subprocess on port E2E_PORT."""
    env = {
        "DB_HOST": E2E_DB_HOST,
        "DB_USER": E2E_DB_USER,
        "DB_PASSWORD": E2E_DB_PASS,
        "DB_NAME": E2E_DB_NAME,
        "DB_PORT": str(E2E_DB_PORT),
        "SECRET_KEY": "e2e-test-secret-not-for-production",
        "FLASK_DEBUG": "False",
        "SCHEDULER_ENABLED": "false",
        "PORT": str(E2E_PORT),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    }

    proc = subprocess.Popen(
        ["python", "app.py"],
        cwd=_PROJECT_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if not _wait_for_port("localhost", E2E_PORT, timeout=20):
        proc.terminate()
        pytest.fail(f"Flask E2E server did not start on port {E2E_PORT} within 20 s")

    base_url = f"http://localhost:{E2E_PORT}"
    yield base_url

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def _playwright_browser():
    """Single Playwright browser instance for the whole test session."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(_playwright_browser):
    """Fresh browser page per test (function scope)."""
    context = _playwright_browser.new_context()
    pg = context.new_page()
    yield pg
    context.close()


@pytest.fixture
def logged_in_page(page, live_server):
    """Page already authenticated as the E2E test user."""
    page.goto(f"{live_server}/login")
    page.locator("#username").fill(E2E_USER)
    page.locator("#password").fill(E2E_PASS)
    page.locator("button[type='submit']").click()
    page.wait_for_url(f"**/painel", timeout=10_000)
    return page
