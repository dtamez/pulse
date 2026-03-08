import asyncio
import hashlib
import secrets

from core.database import async_session
from core.models import ApiKey, Tenant


async def bootstrap():
    async with async_session() as session:
        tenant = Tenant(
            external_key="acme",
            name="Acme Corp",
        )
        session.add(tenant)
        await session.flush()  # assigns tenant.id before commit

        raw_key = f"pulse_{secrets.token_hex(16)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        api_key = ApiKey(
            tenant_id=tenant.id,
            name="default",
            key_hash=key_hash,
        )
        session.add(api_key)

        await session.commit()

        print(f"Created Tenant: {tenant.external_key}")
        print(f"API key: {raw_key}")  # pulse_243815f0d3ef782202c235976185d2ee


if __name__ == "__main__":
    asyncio.run(bootstrap())
