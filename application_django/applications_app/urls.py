from django.urls import path
from rest_framework_simplejwt.views import (
    TokenVerifyView,
    TokenRefreshView,
    TokenObtainPairView,
)

from applications_app import views
from applications_app.swagger import urlpatterns as doc_urls

urlpatterns = [
    path("api/token/", TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path("api/token/refresh/", TokenRefreshView.as_view(), name='token_refresh'),
    path("api/token/verify/", TokenVerifyView.as_view(), name='token_verify'),

    path('create-document/', views.CreateDocumentView.as_view(), name='create_document'),
    path('edit-document/<int:document_id>/', views.EditDocumentView.as_view(), name='edit_document'),
    path('approve-document/<int:document_id>/', views.ApproveDocumentView.as_view(), name='approve_document'),
    path('sign-document/<int:document_id>/', views.SignDocumentView.as_view(), name='sign_document'),
]

urlpatterns += doc_urls
