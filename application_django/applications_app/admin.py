from django import forms
from django.contrib import admin

from .models import (
    Role,
    Profile,
    Document,
    UserRole,
    DocumentApproval,
    DocumentTemplate,
)


class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(label="Имя", max_length=150)
    last_name = forms.CharField(label="Фамилия", max_length=150)

    class Meta:
        model = Profile
        fields = ['user', 'patronymic', 'first_name', 'last_name']

    def __init__(self, *args, **kwargs):
        super(UserProfileForm, self).__init__(*args, **kwargs)
        self.fields['first_name'].initial = self.instance.user.first_name
        self.fields['last_name'].initial = self.instance.user.last_name

    def save(self, commit=True):
        profile = super(UserProfileForm, self).save(commit=False)
        user = profile.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
            profile.save()
        return profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    form = UserProfileForm
    list_display = ('get_full_name', 'user', 'is_active', 'is_staff', 'date_joined')

    def get_full_name(self, obj):
        return f"{obj.user.last_name} {obj.user.first_name} {obj.patronymic}"
    
    get_full_name.short_description = 'Полное ФИО'
    
    def is_active(self, obj):
        return obj.user.is_active
    
    is_active.boolean = True
    is_active.short_description = 'Активен'
    
    def is_staff(self, obj):
        return obj.user.is_staff
    
    is_staff.boolean = True
    is_staff.short_description = 'Статус персонала'
    
    def date_joined(self, obj):
        return obj.user.date_joined
    
    date_joined.short_description = 'Дата регистрации'


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'file')
    prepopulated_fields = {"slug": ("name",)}

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id",'get_fullname', 'student_id','status', 'auto_mode', 'title',  )
    list_filter = ('status', 'type', 'auto_mode')
    search_fields = ('title', 'student_id',)
    list_display_links=('get_fullname', 'student_id',)

    def get_fullname(self, obj):
        return f"{obj.full_student_data.get('lastname', '')} {obj.full_student_data.get('firstname', '')} {obj.full_student_data.get('patronymic', '')}"
    
    get_fullname.short_description = 'Фамилия Имя Отчество'

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'can_edit', 'can_approve', 'can_sign')
    list_filter = ('role',)
    search_fields = ('user__username',)

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {"slug": ("name",)}

@admin.register(DocumentApproval)
class DocumentApprovalAdmin(admin.ModelAdmin):
    list_display = ('document', 'section_name', 'approved_by', 'approved_at', 'approved', 'canceled')
    list_filter = ('approved', 'canceled', 'section_name')
    search_fields = ('document__title', 'approved_by__username', 'section_name')
