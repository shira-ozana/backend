import os

# Settings need these to exist before `app` is imported; real values come from the environment.
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key")
