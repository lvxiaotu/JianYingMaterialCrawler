from .effect import EffectCrawler
from .filter import FilterCrawler
from .flower import FlowerCrawler
from .material_pack import MaterialPackCrawler
from .marketing_template import MarketingTemplateCrawler
from .music import MusicCrawler
from .official_material import OfficialMaterialCrawler
from .sound_effect import SoundEffectCrawler
from .sticker import StickerCrawler
from .subtitle_template import SubtitleTemplateCrawler
from .task_effect import TaskEffectCrawler
from .transition import TransitionCrawler
from .template import TemplateCrawler
from .text_template import TextTemplateCrawler

CRAWLER_MAP = {
    "effect": EffectCrawler,
    "filter": FilterCrawler,
    "flower": FlowerCrawler,
    "marketing_template": MarketingTemplateCrawler,
    "music": MusicCrawler,
    "official_material": OfficialMaterialCrawler,
    "sound_effect": SoundEffectCrawler,
    "sticker": StickerCrawler,
    "subtitle_template": SubtitleTemplateCrawler,
    "task_effect": TaskEffectCrawler,
    "transition": TransitionCrawler,
    "text_template": TextTemplateCrawler,
    "template": TemplateCrawler,
    "material_pack": MaterialPackCrawler,
}
