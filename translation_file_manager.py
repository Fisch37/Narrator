from asyncio import TaskGroup
from os import PathLike
from typing import Any
from discord.app_commands import TranslationContextTypes, Translator, locale_str
from pathlib import Path
import aiofiles
import json

from discord.enums import Locale


class FileSourcedTranslation(Translator):
    def __init__(self, translations_dir: PathLike|str, /) -> None:
        translations_path = translations_dir if isinstance(translations_dir, Path) \
            else Path(translations_dir)
        if not translations_path.exists() or not translations_path.is_dir():
            raise FileNotFoundError(
                f"Translation directory \"{translations_dir}\" does not exist!"
            )
        self.translations_path = translations_path
        self._cached_translations: dict[Locale, dict[str, str]] = {}
        super().__init__()

    async def _load_localisation(self, localisation: Path):
        async with aiofiles.open(localisation) as file:
            # This looks like a type-hint, but it isn't!
            # This is a series of getitem calls.
            # Locale is an EnumMeta type which has its __getitem__ method overridden
            # Locale[a] performs a lookup over the enum
            self._cached_translations[Locale[localisation.stem]] = json.loads(
                await file.read()
            )

    async def load(self) -> None:
        # Eager loading all translations
        async with TaskGroup() as tg:
            for localisation in self.translations_path.iterdir():
                tg.create_task(self._load_localisation(localisation))
        return await super().load()
    
    def get_translation_for_key(self, locale: Locale, key: str) -> str|None:
        return self._cached_translations.get(locale, {}).get(key, None)
    
    async def translate(
        self,
        string: "locale_str",
        locale: Locale,
        context: TranslationContextTypes
    ) -> str | None:
        if locale in self._cached_translations:
            return self.get_translation_for_key(
                locale,
                string.key if isinstance(string, keyed_locale_str) else string.message
            )
        
        return await super().translate(string, locale, context)


class keyed_locale_str(locale_str):
    def __init__(self, message: str, key: str, /, **kwargs: Any) -> None:
        self.key = key
        super().__init__(message, **kwargs)
