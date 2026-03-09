from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_home, name="home"),

    # Users
    path("users/", views.user_list, name="user_list"),
    path("users/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("users/<int:pk>/delete/", views.user_delete, name="user_delete"),

    # Services & Categories
    path("services/", views.service_list, name="service_list"),
    path("services/create/", views.service_create, name="service_create"),
    path("services/<int:pk>/edit/", views.service_edit, name="service_edit"),
    path("services/<int:pk>/delete/", views.service_delete, name="service_delete"),

    path("categories/", views.category_list, name="category_list"),
    path("categories/create/", views.category_create, name="category_create"),
    path("categories/<int:pk>/edit/", views.category_edit, name="category_edit"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),

    # News & news categories
    path("news/", views.news_list, name="news_list"),
    path("news/create/", views.news_create, name="news_create"),
    path("news/<int:pk>/edit/", views.news_edit, name="news_edit"),
    path("news/<int:pk>/delete/", views.news_delete, name="news_delete"),

    path("news/categories/", views.news_category_list, name="news_category_list"),
    path("news/categories/create/", views.news_category_create, name="news_category_create"),
    path("news/categories/<int:pk>/edit/", views.news_category_edit, name="news_category_edit"),
    path("news/categories/<int:pk>/delete/", views.news_category_delete, name="news_category_delete"),
]
