"""
URL configuration for turf_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include




from django.http import JsonResponse

def assetlinks_view(request):
    data = [
      {
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {
          "namespace": "android_app",
          "package_name": "com.adugalam.app",
          "sha256_cert_fingerprints": [
            "B0:72:25:BE:5D:8F:85:1F:40:86:A5:54:3B:DD:E0:B7:F4:02:A7:BD:85:7B:E1:5C:82:4B:24:6E:3F:0C:43:11"
          ]
        }
      }
    ]
    return JsonResponse(data, safe=False)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include('core.urls')),
    path(".well-known/assetlinks.json", assetlinks_view),
]
    #-------- TURF --------

    
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,document_root=settings.MEDIA_ROOT)