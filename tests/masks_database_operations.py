guild = await may_fetch_guild(bot, 734461254747553823)
owner = await may_fetch_member(guild, 582439399938064421)
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