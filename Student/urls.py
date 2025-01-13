from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
      path('login/', views.loginUser, name='login_user'),
    path('verify_otp/<str:email>/', views.verify_otp, name='verify_otp'),
     path('information/', views.getInformation, name='getInformation'),
     path('sign-in/', views.signInUser, name='sign_in'),
      path('upload/', views.upload_file, name='upload_file'),
      path('files/', views.file_list, name='file_list'),
        path('file/<int:pk>/', views.file_detail, name='file_detail'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)