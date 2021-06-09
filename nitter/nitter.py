import logging
import random

from typing import List, Tuple, Type

from mautrix.types import EventType, MessageType
from maubot import Plugin, MessageEvent
from maubot.handlers import command
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper

class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy('twitter')
        helper.copy('youtube')
        helper.copy('bibliogram')

class Nitter(Plugin):
    async def start(self) -> None:
        await super().start()
        self.config.load_and_update()
    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config
    @command.passive(r"(?:www\.)?(twitter\.com|youtube\.com|instagram\.com|youtu\.be)(\/\S+)", multiple=True)
    async def link_handler(self, event: MessageEvent, matches: List[Tuple[str, str]]) -> None:
        await event.mark_read()
        ret = []
        def verify(cfg, key):
            try:
                x = cfg[key][0]
                return True
            except:
                return False
        for match in matches:
            if match[1] == 'twitter.com' and verify(self.config, "twitter"):
                ret.append('https://' + random.choice(self.config["twitter"]) + match[2])
            elif match[1] == 'youtube.com' and verify(self.config, "twitter"):
                ret.append('https://' + random.choice(self.config["youtube"]) + match[2])
            elif match[1] == 'youtu.be' and verify(self.config, "twitter"):
                ret.append('https://' + random.choice(self.config["youtube"]) + '/watch?v=' + match[2][1:])
            elif match[1] == 'instagram.com' and verify(self.config, "bibliogram"):
                if match[2].startswith('/p/'):
                    ret.append('https://' + random.choice(self.config["bibliogram"]) + match[2])
                else:
                    ret.append('https://' + random.choice(self.config["bibliogram"]) + '/u' + match[2])
        if len(ret) > 0:
            await event.respond('\n'.join(ret))
