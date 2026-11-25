// Throwaway test-only secrets (64 chars). Real ones live in .env.local, never in git.
process.env.AUTH_SECRET = "test-auth-secret-0123456789-abcdefghijklmnopqrstuvwxyz-ABCDEFGHIJ";
process.env.BACKEND_JWT_SECRET = "test-service-secret-0123456789-abcdefghijklmnopqrstuvwxyz-ABCDEF";
process.env.MONGODB_URI = "mongodb://127.0.0.1:27017/quorix-test";
process.env.FASTAPI_BASE_URL = "http://backend.test";
