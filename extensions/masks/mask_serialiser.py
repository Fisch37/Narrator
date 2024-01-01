from pydantic import BaseModel

from data.sql.ormclasses import Mask as SQLMask

class Field(BaseModel):
    name: str
    value: str
    inline: bool


class Mask(BaseModel):
    name: str
    # owner_id and guild_id are not represented here.
    # These should be applied by the deserialization.
    description: str
    avatar_url: str|None
    fields: list[Field]


def jsonify(mask: SQLMask) -> Mask:
    """
    Converts an ORM object into a pydantic model.
    """
    return Mask(
        name=mask.name,
        description=mask.description,
        avatar_url=mask.avatar_url,
        fields=[
            Field(
                name=field.name,
                value=field.value,
                inline=field.inline
            )
            for field in mask.fields
        ]
    )

def dejsonify(json_obj: Mask) -> SQLMask:
    """
    Converts an instance of the `Mask` model 
    back into an ORM object with the fields
    `id`, `owner_id`, and `guild_id` being None.
    """
    return SQLMask(
        json_obj.name,
        # Yes these aren't supposed to be nullable, but trust me, I'm an engineer
        None,
        None,
        json_obj.description,
        json_obj.avatar_url
    )

def serialize(mask: SQLMask) -> str:
    """
    Serializes an SQLMask into a JSON-string
    using this module's `jsonify` function.
    
    The result is a string version
    of the `Mask` TypedDict.
    """
    return jsonify(mask).model_dump_json()

def deserialize(string: str) -> SQLMask:
    """
    Converts a JSON string into an SQLMask
    leaving `id`, `owner_id`, and `guild_id` None.
    """
    return dejsonify(Mask.model_validate_json(string))
