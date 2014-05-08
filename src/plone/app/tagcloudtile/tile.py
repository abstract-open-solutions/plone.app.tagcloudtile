from time import time
from operator import itemgetter

from zope.interface import Interface
from zope import schema
from zope.i18n import translate
from zope.component import getMultiAdapter
from zope.component import queryMultiAdapter

from plone.app.vocabularies.catalog import SearchableTextSourceBinder
from plone.app.form.widgets.uberselectionwidget import UberSelectionWidget
from plone.app.layout.navigation.root import getNavigationRoot
from plone.memoize import ram
from plone.tiles import PersistentTile

from Products.PythonScripts.standard import url_quote
from Products.CMFCore.utils import getToolByName

from plone.app.tagcloudtile.vocabularies import SubjectsVocabularyFactory
from plone.app.tagcloudtile.interfaces import IQueryGetter
from plone.app.tagcloudtile import _


def _cachekey(method, self):
    """Time, language, settings based cache
    XXX: If you need to publish private items you should probably
    include the member id in the cache key.
    """
    portal_state = getMultiAdapter((self.context, self.request),
                                   name=u'plone_portal_state')
    portal_url = portal_state.portal_url()
    lang = self.request.get('LANGUAGE', 'en')
    data_string = '-'.join(['%s:%s' % (k, v)
                            for k, v in self.data.items()
                            if v])
    return hash((portal_url, lang, data_string,
                 time() // self.refreshInterval))


class ITagCloudSchema(Interface):

    tile_title = schema.TextLine(
        title=_(u"Tile title"),
        description=_(u"The title of the tagcloud."),
        required=True,
        default=u"Tag Cloud"
    )

    levels = schema.Int(
        title=_(u"Number of different sizes"),
        description=_(u"This number will also determine the biggest size."),
        required=True,
        min=1,
        max=6,
        default=5
    )

    count = schema.Int(
        title=_(u"Maximum number of shown tags."),
        description=_(u"If greater than zero this number will limit the "
                      u"tags shown."),
        required=True,
        min=0,
        default=0)

    restrictSubjects = schema.List(
        required=False,
        title=_(u"Restrict by keywords"),
        description=_(u"Restrict the keywords searched. Leaving "
                      u"this empty will include all keywords"),
        value_type=schema.Choice(
            vocabulary='plone.app.tagcloudtile.subjects'
        ),
        default=[]
    )

    filterSubjects = schema.List(
        required=False,
        title=_(u"Filter by keywords"),
        description=_(u"Filter the keywords searched. Only items "
                      u"categorized with at least all the keywords selected here "
                      u"will be searched. The keywords selected here will be "
                      u"omitted from the tag clouds. Leaving the field empty will "
                      u"disable filtering"),
        value_type=schema.Choice(
            vocabulary='plone.app.tagcloudtile.subjects'
        ),
        default=[]
    )

    restrictTypes = schema.List(
        required=False,
        title=_(u"Restrict by types"),
        description=_(u"Restrict the content types. Leaving this empty "
                      u"will include all user-friendly content types."),
        value_type=schema.Choice(
            vocabulary='plone.app.vocabularies.ReallyUserFriendlyTypes'
        ),
        default=[]
    )

    # see http://stackoverflow.com/questions/16697351/tile-edit-view-wrong-context-for-vocabularies
    # root = schema.Choice(
    #     title=_(u"Root node"),
    #     description=_(u"You may search for and choose a folder "
    #                   u"to act as the root of the navigation tree. "
    #                   u"Leave blank to use the Plone site root."),
    #     required=False,
    #     source=SearchableTextSourceBinder(
    #         {'is_folderish': True},
    #         default_query='path:'
    #     )
    # )

    wfStates = schema.List(
        required=True,
        title=_(u"Workflow states to show"),
        description=_(u"Which workflow states to include in the search"),
        value_type=schema.Choice(
            vocabulary='plone.app.vocabularies.WorkflowStates'
        ),
        default=[]
    )

    refreshInterval = schema.Int(
        title=_(u"Refresh interval"),
        description=_(u"The maximum time in seconds for which the portal"
                      u" will cache the results. Be careful not to use low values."),
        required=True,
        min=1,
        default=3600,
    )


class TagCloud(PersistentTile):

    @property
    def portal_url(self):
        return getToolByName(self.context, 'portal_url')()

    @property
    def catalog(self):
        return getToolByName(self.context, 'portal_catalog')

    @property
    def putils(self):
        return getToolByName(self.context, 'plone_utils')

    def _tile_prop(self, name):
        return self.data[name]

    @property
    def levels(self):
        name = 'levels'
        return self._tile_prop(name) or 5

    @property
    def wfStates(self):
        name = 'wfStates'
        return self._tile_prop(name) or []

    @property
    def count(self):
        name = 'count'
        return self._tile_prop(name) or 0

    @property
    def refreshInterval(self):
        name = 'refreshInterval'
        return self._tile_prop(name) or 3600

    @property
    def restrictTypes(self):
        name = 'restrictTypes'
        return self._tile_prop(name) or []

    @property
    def filterSubjects(self):
        name = 'filterSubjects'
        # XXX: defaults from schema are not taken into account!!
        return self._tile_prop(name) or []

    @property
    def restrictSubjects(self):
        name = 'restrictSubjects'
        # XXX: defaults from schema are not taken into account!!
        return self._tile_prop(name) or []

    @property
    def root(self):
        # name = 'levels'
        # return self._tile_prop(name) or None
        # XXX: DISABLED
        return None

    @ram.cache(_cachekey)
    def getTags(self):
        tagOccs = self.getTagOccurrences()
        # If count has been set sort by occurences and keep the "count" first

        if self.count:
            sortedOccs = sorted(tagOccs.items(),
                                key=itemgetter(1),
                                reverse=True)[:self.count]
            tagOccs = dict(sortedOccs)

        thresholds = self.getThresholds(tagOccs.values())
        tags = tagOccs.keys()
        tags.sort()
        res = []
        for tag in tags:
            item = {}
            size = self.getTagSize(tagOccs[tag], thresholds)
            if size == 0:
                continue
            item["text"] = tag
            item["class"] = "cloud" + str(size)
            href = self.portal_url + "/@@search?Subject%3Alist=" + url_quote(tag)
            #Add type restrictions to search link
            href = href + "".join([
                "&portal_type%3Alist=" + url_quote(ptype)
                for ptype in self.restrictTypes
            ])
            #Add workflow restrictions to search link
            href = href + "".join([
                "&review_state%3Alist=" + url_quote(wstate)
                for wstate in self.wfStates
            ])
            #Add path to search link
            if self.root:
                nav_root = getNavigationRoot(self.context,
                                             relativeRoot=self.root)
                href = href + "&path=%s" % nav_root
            item["href"] = href
            msg = _(u'${count} items', mapping={'count': tagOccs[tag]})
            item["count"] = translate(msg, context=self.request)
            res.append(item)
        return res

    @property
    def tile_title(self):
        return self.data['tile_title']

    def getSearchSubjects(self):
        if self.restrictSubjects:
            result = self.restrictSubjects
        else:
            result = list(self.catalog.uniqueValuesFor('Subject'))
        for filtertag in self.filterSubjects:
            if filtertag in result:
                result.remove(filtertag)
        return result

    def getSearchTypes(self):
        if self.restrictTypes:
            return self.restrictTypes
        else:
            return self.putils.getUserFriendlyTypes()

    def getTagOccurrences(self):
        types = self.getSearchTypes()
        tags = self.getSearchSubjects()
        filterTags = self.filterSubjects
        tagOccs = {}
        query = {}
        query['portal_type'] = types
        if self.root:
            query['path'] = getNavigationRoot(
                self.context,
                relativeRoot=self.root)
        if self.wfStates:
            query['review_state'] = self.wfStates

        query_getter = queryMultiAdapter((self, self.context), IQueryGetter)
        if query_getter:
            query.update(query_getter(**query))

        for tag in tags:
            result = []
            if filterTags:
                query['Subject'] = {'query': filterTags + [tag],
                                    'operator': 'and'}
            else:
                query['Subject'] = tag
            result = self.catalog.searchResults(**query)
            if result:
                tagOccs[tag] = len(result)

        return tagOccs

    def getTagSize(self, tagWeight, thresholds):
        size = 0
        if tagWeight:
            for t in thresholds:
                size += 1
                if tagWeight <= t:
                    break
        return size

    def getThresholds(self, sizes):
        """This algorithm was taken from Anders Pearson's blog:
         http://thraxil.com/users/anders/posts/2005/12/13/scaling-tag-clouds/
        """
        if not sizes:
            return [1 for i in range(0, self.levels)]
        minimum = min(sizes)
        maximum = max(sizes)
        return [pow(maximum - minimum + 1,
                    float(i) / float(self.levels))
                for i in range(0, self.levels)]

    @property
    def available(self):
        return self.getSearchTypes() and self.getSearchSubjects()


# class AddForm(base.AddForm):
#     """
#     """

#     form_fields = form.Fields(ITagCloudTile)
#     form_fields['root'].custom_widget = UberSelectionWidget

#     def create(self, data):
#         """
#         """
#         return Assignment(**data)


# class EditForm(base.EditForm):
#     """
#     """
#     form_fields = form.Fields(ITagCloudTile)
#     form_fields['root'].custom_widget = UberSelectionWidget

#     def __call__(self):
#         subjectFields = ['restrictSubjects', 'filterSubjects']
#         for fieldname in subjectFields:
#             field = self.form_fields.get(fieldname).field
#             existing = field.get(self.context)
#             subject_vocab = SubjectsVocabularyFactory(self.context)
#             all_subjects = set([t.title for t in subject_vocab])
#             valid = all_subjects.intersection(existing)
#             if not valid == set(existing):
#                 field.set(self.context, list(valid))
#         return super(EditForm, self).__call__()
