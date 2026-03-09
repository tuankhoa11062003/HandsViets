from django.contrib import admin
from .models import (
    ExerciseLog,
    ExerciseProfile,
    Lead,
    NewsArticle,
    NewsCategory,
    Package,
    PatientProfile,
    ProgressNote,
    Purchase,
    Service,
    ServiceCategory,
    SessionSchedule,
    Transaction,
    Video,
)

admin.site.register(ServiceCategory)
admin.site.register(Service)
admin.site.register(NewsCategory)
admin.site.register(NewsArticle)
admin.site.register(Lead)
admin.site.register(Package)
admin.site.register(Purchase)
admin.site.register(Video)
admin.site.register(SessionSchedule)
admin.site.register(PatientProfile)
admin.site.register(ProgressNote)
admin.site.register(ExerciseProfile)
admin.site.register(ExerciseLog)
admin.site.register(Transaction)
