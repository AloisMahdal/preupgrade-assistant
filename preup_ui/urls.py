from django.conf.urls import patterns, include, url

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
from preup_ui.auth.views import FirstRunView, FirstRunDisableAuthView, login
from preup_ui.auth.decorators import first_run_required as frr

admin.autodiscover()

urlpatterns = patterns('',
    url(r'^', include('preup_ui.report.urls')),

    #url(r'^settings/', include('preup_ui.config.urls')),

    url(r"^xmlrpc/", include("preup_ui.xmlrpc_backend.urls"), name="xmlrpc"),

    # shortcut for XML-RPC submission
    url(r"^submit/$", "preup_ui.xmlrpc_backend.views.submission_handler", name="xmlrpc-submit"),

    url(r'^admin/', include(admin.site.urls)),

    url(r'^compare/', include('preup_ui.compare.urls')),

    # private auth URLs
    url(r'^auth/', include('preup_ui.auth.urls')),

    # public auth URLs -- first display and login itself
    url(r'^login/$', login, {'template_name': 'auth/login.html'}, name='auth-login'),
    url(r'^first/$', frr(FirstRunView.as_view()), name='first-run'),
    url(r'^first/disable/$', frr(FirstRunDisableAuthView.as_view()), name='first-run-disable-auth'),
)

