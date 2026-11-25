"""Result shapes returned by the quick-commerce tools."""

from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["ok", "needs_login", "needs_location", "not_found", "error"]


class Product(BaseModel):
    """One product card read from a site."""

    name: str
    price: str | None = None
    mrp: str | None = None
    pack: str | None = None
    url: str | None = None


class SiteInfo(BaseModel):
    """A supported store."""

    id: str
    name: str
    home: str


class SiteCatalog(BaseModel):
    """Stores this server can operate."""

    sites: list[SiteInfo]
    login: str = Field(
        description="How a person signs in. The server never asks for or stores a password or OTP."
    )


class SiteResult(BaseModel):
    """What one site showed for a search, login check, or cart action."""

    site: str
    site_name: str
    status: Status
    message: str
    products: list[Product] = Field(default_factory=list)


class CompareResult(BaseModel):
    """The same search run on every supported site."""

    query: str
    sites: list[SiteResult]
