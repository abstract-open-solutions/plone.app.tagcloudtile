#-*- coding: utf-8 -*-

from zope.interface import Interface
from plone.theme.interfaces import IDefaultPloneLayer


class ILayer(IDefaultPloneLayer):
    """Browser layer for plone theme package
    """


class IQueryGetter(Interface):
    """ adapter for tile and context that allows to customize
        the query for getting subjects to list programmatically.
    """

    def __call__(**kw):
        """ return a dict with query params
        ``kw`` defaults to default query dict
        """


class ICacheKeyGetter(Interface):
    """ adapter for context and request that allows to customize
        the caching key programmatically.
        Used in combination with a custom `IQueryGetter` adapter
        you can use this to limit the cache to a single folder or
        section.
    """

    def __call__(**kw):
        """ returns the cache key
        ``kw`` defaults to tile's data
        """
