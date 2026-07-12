"""Subida de tables/table_*.csv a un bucket de Supabase Storage.

Requiere las variables de entorno SUPABASE_URL y SUPABASE_SERVICE_KEY
(en GitHub Actions se cargan como secrets).
"""

import glob
import logging
import os

logger = logging.getLogger(__name__)


def has_credentials():
    return bool(os.environ.get("SUPABASE_URL")) and bool(os.environ.get("SUPABASE_SERVICE_KEY"))


def upload_tables(tables_dir="tables", bucket="tables"):
    """Sube todos los table_*.csv al bucket con upsert. Devuelve la cantidad subida."""
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError(
            "Faltan SUPABASE_URL y/o SUPABASE_SERVICE_KEY en el entorno"
        )

    from supabase import create_client

    client = create_client(supabase_url, supabase_key)
    storage = client.storage.from_(bucket)

    files = sorted(glob.glob(os.path.join(tables_dir, "table_*.csv")))
    if not files:
        raise RuntimeError(f"No hay table_*.csv en {tables_dir}")

    for path in files:
        name = os.path.basename(path)
        with open(path, "rb") as f:
            data = f.read()
        storage.upload(
            name,
            data,
            file_options={"content-type": "text/csv", "upsert": "true"},
        )
        logger.info("uploaded %s (%d bytes)", name, len(data))

    return len(files)
