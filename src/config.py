from pydantic import AnyUrl, AnyHttpUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DISCORDTOKEN: str
    TOPGZONECHANNELID: int
    JAILROLE: int
    RIOTTOKEN: str
    REDISURL: str
    PLAYERROLE: int
    GROLE: int
    PINGROLE: int
    SUPERUSER: int
    CONFESSIONALCHANNELID: int
    CASHOUTCHANNELID: int
    FANBOYROLEID: int
    HATERROLEID: int
    ROLECHANNELID: int
    LUNCHERS: int
    LEAGUERSID: int
    VARIETYID: int
    LIVEGAMECHANNELID: int


    class Config:
        env_file = ".env"
