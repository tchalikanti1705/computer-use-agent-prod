from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from shared.config import get_settings
from shared.database import TenantStore

security = HTTPBearer(auto_error=False)

def create_jwt_token(tenant_id: str) -> str:
    s = get_settings()
    return jwt.encode({"sub": tenant_id, "exp": datetime.utcnow() + timedelta(minutes=s.jwt_expire_minutes)},
                       s.jwt_secret, algorithm=s.jwt_algorithm)

def decode_jwt_token(token: str) -> dict:
    s = get_settings()
    try: return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except JWTError as e: raise HTTPException(401, f"Invalid token: {e}")

async def get_current_tenant(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    if not credentials: raise HTTPException(401, "Missing authorization")
    token = credentials.credentials
    store = TenantStore()
    if token.startswith("cua_"):
        tenant = store.get_tenant_by_api_key(token)
        if not tenant: raise HTTPException(401, "Invalid API key")
        return tenant
    payload = decode_jwt_token(token)
    tenant = store.get_tenant(payload["sub"])
    if not tenant: raise HTTPException(401, "Tenant not found")
    return tenant
