def shard_for_tenant(external_key: str) -> str:
    if external_key[0].lower() <= "m":
        return "shard1"
    return "shard2"
