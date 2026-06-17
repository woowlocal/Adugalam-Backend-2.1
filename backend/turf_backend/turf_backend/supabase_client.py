"""
Supabase client singleton for the turf_backend project.

Usage in any Django view or service:
    from turf_backend.supabase_client import supabase

    response = supabase.table('todos').select("*").execute()
    data = response.data
"""

import os
# pyrefly: ignore [missing-import]
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

supabase: Client = create_client(
    os.environ.get("SUPABASE_URL"),
    os.environ.get("SUPABASE_KEY"),
)
