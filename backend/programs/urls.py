from django.urls import path
from programs import views

app_name = 'programs'

urlpatterns = [
    # Program Management
    path('', views.program_list, name='program_list'),
    path('add/', views.add_program, name='add_program'),
    path('<int:program_id>/update/', views.update_program, name='update_program'),
    path('<int:program_id>/delete/', views.delete_program, name='delete_program'),
    path('<int:program_id>/', views.program_detail, name='program_detail'),

    # Program sections
    path('programs/<int:program_id>/sections/add/', views.add_program_section, name='add_program_section'),
    path('programs/<int:program_id>/sections/<int:section_id>/update/', views.update_program_section, name='update_program_section'),
    path('programs/<int:program_id>/sections/<int:section_id>/delete/', views.delete_program_section, name='delete_program_section'),

    # Program Courses
    path('programs/<int:program_id>/courses/add/', views.attach_program_course, name='attach_program_course'),
    path('programs/<int:program_id>/courses/<int:program_course_id>/remove/', views.remove_program_course, name='remove_program_course'),

    # Course Catalogue
    path('courses/', views.course_list, name='course_list'),
    path('courses/add/', views.add_course, name='add_course'),
    path('courses/<int:course_id>/update/', views.update_course, name='update_course'),
    path('courses/<int:course_id>/delete/', views.delete_course, name='delete_course'),
]
