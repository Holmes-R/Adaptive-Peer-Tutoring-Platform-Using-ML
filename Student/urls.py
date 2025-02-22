from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
from .views import *
urlpatterns = [
     path('', loginUser, name='login'),
    path('verify_otp/<str:email>/', views.verify_otp, name='verify_otp'),
     path('information/', views.getInformation, name='getInformation'),
     path('sign-in/', views.signInUser, name='sign_in'),
      path('upload/', views.upload_file, name='upload_file'),
      path('files/', views.file_list, name='file_list'),
      path('file/<int:pk>/summary/', views.summary_detail, name='summary_detail'),
    path('file/<int:pk>/keywords/', views.keywords_detail, name='keywords_detail'),
    path('submit_feedback_summary/', views.submit_feedback_summary, name='submit_feedback_summary'),
    path('submit_feedback_keywords/', views.submit_feedback_keywords, name='submit_feedback_keywords'),
      path('adlog/', views.admin_login, name='login'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)