import aiohttp
import dataclasses
import random

from typing import Dict, List, Optional, Tuple, Type, Union

from mautrix.types import EventType
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from maubot import Plugin, MessageEvent
from maubot.handlers import command
from maubot.handlers.command import CommandHandler, CommandHandlerFunc

NSFW_STATE_CHANGE_LEVEL = EventType.find("org.pavluk.nekogirl.nsfw_manage_level", t_class=EventType.Class.STATE)
NSFW_STATE = EventType.find("org.pavluk.nekogirl.nsfw", t_class=EventType.Class.STATE)

@dataclasses.dataclass
class Image:
    url: str
    extension: Optional[str] = None

class ImageSource:
    async def fetch(self) -> str:
        raise NotImplementedError()

class NekosLifeSource(ImageSource):
    def __init__(self, *, nsfw: bool, gif: bool):
        if nsfw and not gif:
            suf = "lewd"
        elif nsfw and gif:
            suf = "nsfw_neko_gif"
        elif not nsfw and not gif:
            suf = "neko"
        elif not nsfw and gif:
            suf = "ngif"
        self.url = f"https://nekos.life/api/v2/img/{suf}"
    async def fetch(self) -> Image:
        async with aiohttp.ClientSession() as session:
            async with session.get(self.url) as response:
                json = await response.json()
                return Image(json["url"])

class NekoLoveXyzSource(ImageSource):
    def __init__(self, *, nsfw: bool):
        if nsfw:
            self.url = "https://neko-love.xyz/api/v1/nekolewd"
        else:
            self.url = "https://neko-love.xyz/api/v1/neko"
    async def fetch(self) -> Image:
        async with aiohttp.ClientSession() as session:
            async with session.get(self.url) as response:
                json = await response.json()
                return Image(json["url"])

class NekosMoeSource(ImageSource):
    def __init__(self, *, nsfw: bool):
        if nsfw:
            self.url = "https://nekos.moe/api/v1/random/image?nsfw=true"
        else:
            self.url = "https://nekos.moe/api/v1/random/image?nsfw=false"
    async def fetch(self) -> Image:
        async with aiohttp.ClientSession() as session:
            async with session.get(self.url) as response:
                json = await response.json()
                id = json["images"][0]["id"]
                url = f"https://nekos.moe/image/{id}"
                return Image(url)

@dataclasses.dataclass
class CustomImageDefinition:
    url: str
    extension: Optional[str]
    chance: Union[float, int]

    def image(self):
        return Image(self.url, self.extension)

class CustomImageSource(ImageSource):
    defs: List[CustomImageDefinition]
    total: float
    
    def __init__(self, defs: List[dict], *, gif: Optional[bool]):
        self.defs = []
        self.total = 0.0
        for d in defs:
            if gif is not None and (d.get("extension") in ["apng", "gif"]) != gif:
                continue
            self.total += d.get("chance", 1.0)
            self.defs.append(CustomImageDefinition(
                d["url"],
                d.get("extension", None),
                d.get("chance", 1.0)
            ))
    async def fetch(self) -> Image:
        n = random.random() * self.total
        m = 0.0
        for d in self.defs:
            m += d.chance
            if m > n:
                return d.image()
        raise RuntimeError('Unexpected issue occured')

class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("sfw")
        helper.copy("nsfw")
        helper.copy("custom_tags")

@dataclasses.dataclass
class SourceDefinition:
    source: ImageSource
    chance: Union[int, float]

@dataclasses.dataclass
class CustomTag:
    nsfw: bool
    source: CustomImageSource

class SourceSet:
    sources: List[SourceDefinition]
    total: float
    
    def __init__(self, sources, total):
        self.sources = sources
        self.total = total
    
    def update_total(self):
        self.total = 0.0
        for source in self.sources:
            self.total += source.chance
    
    def choose(self) -> ImageSource:
        n = random.random() * self.total
        m = 0.0
        for source in self.sources:
            m += source.chance
            if m > n:
                return source.source
        raise RuntimeError('Unexpected issue occured')

class SfwSourceSet(SourceSet):
    def __init__(self, config):
        self.sources = [
            SourceDefinition(
                NekosLifeSource(nsfw=False, gif=False),
                config["sfw"]["nekos_life"]["chance"]
            ),
            SourceDefinition(
                NekoLoveXyzSource(nsfw=False),
                config["sfw"]["neko_love_xyz"]["chance"]
            ),
            SourceDefinition(
                NekosMoeSource(nsfw=False),
                config["sfw"]["nekos_moe"]["chance"]
            ),
            SourceDefinition(
                CustomImageSource(config["sfw"]["images"]["options"], gif=False),
                config["sfw"]["images"]["chance"],
            ),
        ]
        if not self.sources[3].source.defs:
            self.sources.pop()
        self.update_total()

class SfwGifSourceSet(SourceSet):
    def __init__(self, config):
        self.sources = [
            SourceDefinition(
                NekosLifeSource(nsfw=False, gif=True),
                config["sfw"]["nekos_life"]["gif_chance"]
            ),
            SourceDefinition(
                CustomImageSource(config["sfw"]["images"]["options"], gif=True),
                config["sfw"]["images"]["gif_chance"],
            ),
        ]
        if not self.sources[1].source.defs:
            self.sources.pop()
        self.update_total()

class NsfwSourceSet(SourceSet):
    def __init__(self, config):
        self.sources = [
            SourceDefinition(
                NekosLifeSource(nsfw=True, gif=False),
                config["nsfw"]["nekos_life"]["chance"]
            ),
            SourceDefinition(
                NekoLoveXyzSource(nsfw=True),
                config["nsfw"]["neko_love_xyz"]["chance"]
            ),
            SourceDefinition(
                NekosMoeSource(nsfw=True),
                config["nsfw"]["nekos_moe"]["chance"]
            ),
            SourceDefinition(
                CustomImageSource(config["nsfw"]["images"]["options"], gif=False),
                config["nsfw"]["images"]["chance"],
            ),
        ]
        if not self.sources[3].source.defs:
            self.sources.pop()
        self.update_total()

class NsfwGifSourceSet(SourceSet):
    def __init__(self, config):
        self.sources = [
            SourceDefinition(
                NekosLifeSource(nsfw=True, gif=True),
                config["nsfw"]["nekos_life"]["gif_chance"]
            ),
            SourceDefinition(
                CustomImageSource(config["nsfw"]["images"]["options"], gif=True),
                config["nsfw"]["images"]["gif_chance"],
            ),
        ]
        if not self.sources[1].source.defs:
            self.sources.pop()
        self.update_total()

class Nekogirl(Plugin):
    sfw_sources: SourceSet
    nsfw_sources: SourceSet
    sfw_gif_sources: SourceSet
    nsfw_gif_sources: SourceSet
    custom_tags: Dict[str, CustomTag]
    custom_tags_no_alias: Dict[str, CustomTag]
    
    async def start(self) -> None:
        self.sfw_sources = SourceSet([], 0.0)
        self.nsfw_sources = SourceSet([], 0.0)
        self.sfw_gif_sources = SourceSet([], 0.0)
        self.nsfw_gif_sources = SourceSet([], 0.0)
        self.custom_tags = {}
        self.custom_tags_no_alias = {}
        await super().start()
        self.on_external_config_update()
    
    def on_external_config_update(self):
        self.config.load_and_update()
        self.custom_tags = {}
        self.custom_tags_no_alias = {}
        self.sfw_sources = SfwSourceSet(self.config)
        self.nsfw_sources = NsfwSourceSet(self.config)
        self.sfw_gif_sources = SfwGifSourceSet(self.config)
        self.nsfw_gif_sources = NsfwGifSourceSet(self.config)
        if self.config["custom_tags"]:
            for k, v in self.config["custom_tags"].items():
                tag = CustomTag(
                    v.get("nsfw", False),
                    CustomImageSource(v["options"], gif=None),
                )
                self.custom_tags[k] = tag
                self.custom_tags_no_alias[k] = tag
                for alias in v.get("aliases", []):
                    self.custom_tags[alias] = tag

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config

    async def can_manage(self, event: MessageEvent) -> bool:
        global NSFW_STATE_CHANGE_LEVEL
        levels = await self.client.get_state_event(event.room_id, EventType.ROOM_POWER_LEVELS)
        user_level = levels.get_user_level(event.sender)
        state_level = levels.get_event_level(NSFW_STATE_CHANGE_LEVEL)
        if not isinstance(state_level, int):
            state_level = 50
        if user_level < state_level:
            return False
        return True

    async def nsfw_allowed(self, event: MessageEvent) -> bool:
        global NSFW_STATE
        if not self.config["nsfw"]["allow"]:
            return False
        try:
            nsfw_allowed = (await self.client.get_state_event(event.room_id, NSFW_STATE))['allow_nsfw']
        except:
            nsfw_allowed = None
        if not isinstance(nsfw_allowed, bool):
            if self.config["nsfw"]["require_nsfw_in_room_name"]:
                try:
                    name = (await self.client.get_state_event(event.room_id, EventType.ROOM_NAME))['name']
                except:
                    name = None
                if not isinstance(name, str) or ("nsfw" not in name.lower() and "18+" not in name):
                    return False
            return True
        return nsfw_allowed

    async def reply_with_source(self, event: MessageEvent, source: ImageSource) -> None:
        image = await source.fetch()
        if image.url.startswith('mxc:'):
            mime = f"image/{image.extension}"
            if image.extension in ["jpg", "jfif"]:
                mime = "image/jpeg"
            content = MediaMessageEventContent(
                url=image.url,
                body=f"nekogirl.{image.extension}",
                msgtype=MessageType.IMAGE,
                info=ImageInfo(
                    mimetype=mime
                ),
            )
            await event.respond(content)
        else:
            await event.respond(image.url)
    
    #@command.new("nekogirl", help="Get a nekogirl image", aliases=["catgirl", "neko"])
    #async def stub(self, *args, **kwargs) -> None:
    #    pass
    
    @command.passive("^!(nekogirl|catgirl|neko)(\s|$)")
    async def handler(self, event: MessageEvent, match: Tuple[str]) -> None:
        global NSFW_STATE
        tags = list(map(str.lower, event.content.body.split()[1:]))
        if "help" in tags:
            available_tags = ["gif"]
            if self.config["nsfw"]["allow"]:
                available_tags.append("lewd")
                available_tags.extend(self.custom_tags_no_alias.keys())
            else:
                available_tags.extend(k for k, v in self.custom_tags_no_alias.items() if not v.nsfw)
            help_msg = """Available commands:

`nekogirl help`

`nekogirl enable_nsfw`

`nekogirl disable_nsfw`

`nekogirl [tags]`

Available tags: """ + "/".join(available_tags)
            await event.reply(help_msg)
            return
        if "enable_nsfw" in tags:
            if not await self.can_manage(event):
                await event.reply("You don't have the permission to change NSFW settings in this room!")
                return
            try:
                await self.client.send_state_event(event.room_id, NSFW_STATE, {'allow_nsfw': True})
                await event.reply('NSFW enabled!')
            except:
                await event.reply("Failed to change room settings! Perhaps the bot user's permissions are insufficient?")
            return
        if "disable_nsfw" in tags:
            if not await self.can_manage(event):
                await event.reply("You don't have the permission to change NSFW settings in this room!")
                return
            try:
                await self.client.send_state_event(event.room_id, NSFW_STATE, {'allow_nsfw': False})
                await event.reply('NSFW disabled!')
            except:
                await event.reply("Failed to change room settings! Perhaps the bot user's permissions are insufficient?")
            return
        nsfw = (("lewd" in tags) or ("nsfw" in tags) or ("hentai" in tags)) and self.config["nsfw"]["allow"]
        custom = None
        for k, v in self.custom_tags.items():
            if k in tags:
                if not v.nsfw or self.config["nsfw"]["allow"]:
                    custom = self.custom_tags[k]
                    nsfw = v.nsfw
                    break
        gif = ("gif" in tags) or ("animated" in tags) or ("video" in tags)
        if nsfw and not await self.nsfw_allowed(event):
            await event.reply("NSFW not allowed in this room! Room moderators can use the `nekogirl enable_nsfw` command")
            return
        if custom is not None:
            source = custom.source
        elif nsfw and gif:
            source = self.nsfw_gif_sources.choose()
        elif nsfw and not gif:
            source = self.nsfw_sources.choose()
        elif not nsfw and gif:
            source = self.sfw_gif_sources.choose()
        elif not nsfw and not gif:
            source = self.sfw_sources.choose()
        await self.reply_with_source(event, source)
