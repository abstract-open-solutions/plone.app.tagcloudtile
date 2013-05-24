from plone.app.testing import PloneWithPackageLayer
from plone.app.testing import IntegrationTesting
from plone.app.testing import FunctionalTesting

import plone.app.tagcloudtile


PLONE_APP_TAGCLOUDTILE = PloneWithPackageLayer(
    zcml_package=plone.app.tagcloudtile,
    zcml_filename='testing.zcml',
    gs_profile_id='plone.app.tagcloudtile:testing',
    name="PLONE_APP_TAGCLOUDTILE")

PLONE_APP_TAGCLOUDTILE_INTEGRATION = IntegrationTesting(
    bases=(PLONE_APP_TAGCLOUDTILE, ),
    name="PLONE_APP_TAGCLOUDTILE_INTEGRATION")

PLONE_APP_TAGCLOUDTILE_FUNCTIONAL = FunctionalTesting(
    bases=(PLONE_APP_TAGCLOUDTILE, ),
    name="PLONE_APP_TAGCLOUDTILE_FUNCTIONAL")
