from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),

    # ✅ LOGIN PAGE IS ROOT (/)
    path('', auth_views.LoginView.as_view(
        template_name='registration/login.html'
    ), name='login'),

    # optional: still allow /accounts/login/
    path('accounts/login/', auth_views.LoginView.as_view(
        template_name='registration/login.html'
    )),

    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('feedback/', include('feedback.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('facilities/', include('facilities.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
