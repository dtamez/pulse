import asyncio
import hashlib
import secrets

from sqlalchemy import select

from core.database import async_session
from core.models import ApiKey, Tenant

raw_keys = {}

tenants = [
    Tenant(external_key="wacky", name="Wacky Widgets"),
    Tenant(external_key="quirky", name="Quirky Quokkas"),
    Tenant(external_key="silly", name="Silly Snacks"),
    Tenant(external_key="cheesy", name="Cheesy Churros"),
    Tenant(external_key="merry", name="Merry Milkshakes"),
    Tenant(external_key="loony", name="Loony Llamas"),
    Tenant(external_key="zany", name="Zany Zucchini"),
    Tenant(external_key="giggle", name="Giggle Gadgets"),
    Tenant(external_key="doodle", name="Doodle Doughnuts"),
    Tenant(external_key="smiley", name="Smiley Soft Drinks"),
    Tenant(external_key="happy", name="Happy Hiccups"),
    Tenant(external_key="bubbly", name="Bubbly Bottles"),
    Tenant(external_key="jolly", name="Jolly Jellyfish"),
    Tenant(external_key="bouncing", name="Bouncing Bubbles"),
    Tenant(external_key="whimsical", name="Whimsical Waffles"),
    Tenant(external_key="funky", name="Funky Furballs"),
    Tenant(external_key="cozy", name="Cozy Coozies"),
    Tenant(external_key="sunshine", name="Sunshine Sweets"),
    Tenant(external_key="nutty", name="Nutty Nuggets"),
    Tenant(external_key="playful", name="Playful Pies"),
]


async def bootstrap():
    async with async_session() as session:
        for tenant in tenants:
            # skip if tenant already exists
            existing = await session.scalar(
                select(Tenant).where(Tenant.external_key == tenant.external_key)
            )
            if existing:
                print(f"Skipped existing tenant: {tenant.external_key}")
                continue

            session.add(tenant)
            await session.flush()  # tenant.id available now

            raw_key = f"pulse_{secrets.token_hex(16)}"
            key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

            session.add(
                ApiKey(
                    tenant_id=tenant.id,
                    name="default",
                    key_hash=key_hash,
                )
            )

            raw_keys[tenant.external_key] = raw_key
            print(f"Created tenant: {tenant.external_key}")

        await session.commit()

    print(raw_keys)


if __name__ == "__main__":
    asyncio.run(bootstrap())
