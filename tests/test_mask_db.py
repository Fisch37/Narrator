from unittest.mock import Mock
from random import randrange

from data.sql.ormclasses import Mask, MaskField
from data.sql.engine import AsyncDatabase


def get_owner() -> Mock:
    return Mock(
        id=randrange(2**63, 2**64),
        guild=Mock(id=randrange(2**63, 2**64))
    )


async def database_seq():
    owner = get_owner()
    mask = await Mask.new(name="Alice", owner=owner)
    print("After creation", mask)
    mask.name = "Alice"
    mask.description = "This is Alice. She is not Bob."
    mask.fields.append(MaskField(name="Pronouns", value="she/her", inline=True))
    print("After setting", mask)
    await mask.update()
    print("After update", mask)
    mask2 = await Mask.get(mask.id)
    print("After reaquire", mask2)
    if mask2 is None:
        return
    await mask2.delete()
    print("After deletion", mask2)
    mask3 = await Mask.get(mask2.id)
    print("After deletion-acquire", mask3)


async def test():
    async with AsyncDatabase("sqlite+aiosqlite:///:memory:"):
        await database_seq()

# if __name__ == "__main__":
#     run(test())
