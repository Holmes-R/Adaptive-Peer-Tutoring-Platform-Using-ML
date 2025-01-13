from django.apps import AppConfig
import nltk


class StudentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Student'

    def ready(self):
        nltk.download('all')