import os

from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.contrib.auth.models import User
from django.utils.deconstruct import deconstructible


@deconstructible
class UploadToPathAndRename:
    def __init__(self, path):
        self.sub_path = path

    def __call__(self, instance, filename):
        ext = filename.split(".")[-1]
        filename = f"{instance.slug}.{ext}"
        return os.path.join(self.sub_path, filename)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    patronymic = models.CharField(
        max_length=255, verbose_name="Отчество", blank=True, null=True
    )

    class Meta:
        verbose_name = "Профиль"
        verbose_name_plural = "Профили"

    def __str__(self):
        return f"{self.user.last_name} {self.user.first_name} {self.patronymic}"


class Role(models.Model):
    name = models.CharField(max_length=255, verbose_name="Название роли")
    slug = models.SlugField(max_length=255, unique=True, verbose_name="Slug")

    class Meta:
        verbose_name = "Роль"
        verbose_name_plural = "Роли"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class UserRole(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="role", verbose_name="Пользователь"
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="user_roles",
        verbose_name="Роль в организации",
    )
    can_edit = models.BooleanField(default=False, verbose_name="Может редактировать")
    can_approve = models.BooleanField(default=False, verbose_name="Может утверждать")
    can_sign = models.BooleanField(default=False, verbose_name="Может подписывать")

    class Meta:
        verbose_name = "Роль пользователя"
        verbose_name_plural = "Роли пользователей"

    def __str__(self):
        permissions = []
        if self.can_edit:
            permissions.append("Редактирует")
        if self.can_approve:
            permissions.append("Утверждает")
        if self.can_sign:
            permissions.append("Подписывает")
        return (
            f'{self.user.username} ({self.role.name}) - права: {", ".join(permissions)}'
        )


class DocumentTemplate(models.Model):
    name = models.CharField(max_length=255, verbose_name="Название шаблона")
    slug = models.SlugField(max_length=255, unique=True, verbose_name="Slug")
    file = models.FileField(
        upload_to=UploadToPathAndRename("document_templates/"),
        verbose_name="Файл шаблона",
    )

    class Meta:
        verbose_name = "Шаблон документа"
        verbose_name_plural = "Шаблоны документов"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)

        old_file = self.file.name
        super().save(*args, **kwargs)

        new_file = os.path.join(
            "document_templates", f'{self.slug}.{self.file.name.split(".")[-1]}'
        )
        if old_file != new_file:
            os.rename(self.file.path, os.path.join(settings.MEDIA_ROOT, new_file))
            self.file.name = new_file
            super().save(update_fields=["file"])

    def __str__(self):
        return self.name


class DocumentApproval(models.Model):
    document = models.ForeignKey(
        "Document",
        on_delete=models.CASCADE,
        related_name="approvals",
        verbose_name="Документ",
    )
    section_name = models.CharField(max_length=255, verbose_name="Название секции")
    approved_by = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name="Утверждено пользователем"
    )
    approved_at = models.DateTimeField(auto_now=True, verbose_name="Дата утверждения")
    approved = models.BooleanField(default=True, verbose_name="Подтверждено")
    canceled = models.BooleanField(default=False, verbose_name="Отказано")

    class Meta:
        verbose_name = "Утверждение документа"
        verbose_name_plural = "Утверждения документов"
        unique_together = ("document", "section_name")

    def __str__(self):
        return f"{self.section_name} - утверждено {self.approved_by.username}"


class Document(models.Model):
    STATUS_CHOICES = [
        ("pending", "Ожидает обработки"),
        ("approved_for_editing", "Одобрено для редактирования"),
        ("approved_for_approving", "Одобрено для подтверждения"),
        ("approved_for_signing", "Одобрено для подписания"),
        ("signed", "Подписано"),
        ("canceled", "Отказано"),
    ]

    type = models.SlugField(
        max_length=255, help_text="Тип документа (slug)", verbose_name="Тип документа"
    )
    title = models.CharField(
        max_length=255,
        help_text="Название документа",
        verbose_name="Название документа",
    )
    content = models.JSONField(
        default=dict,
        help_text="Данные документа, заполненные пользователем",
        verbose_name="Содержимое документа",
        null=True,
        blank=True,
    )
    student_id = models.IntegerField(
        help_text="ID студента, связанного с документом", verbose_name="ID студента"
    )
    full_student_data = models.JSONField(
        default=dict,
        help_text="Полный ответ от get_student_data",
        verbose_name="Полные данные студента",
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name="Статус документа",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Дата и время последнего изменения документа",
        verbose_name="Дата последнего изменения",
    )
    required_sections = models.ManyToManyField(
        Role,
        related_name="required_documents",
        verbose_name="Требуемые секции",
        blank=True,
    )
    auto_mode = models.BooleanField(default=True, verbose_name="Автоматический режим")
    created_at = models.DateField(
        verbose_name="Дата создания",
        auto_now_add=True,
        help_text="Дата создания документа. Этот параметр не подлежит изменению.",
    )

    class Meta:
        verbose_name = "Документ"
        verbose_name_plural = "Документы"
        ordering = ["-updated_at"]

    def update_content(self, new_data: dict) -> bool:
        self.content.update(new_data)
        self.save()
        return True

    def __str__(self):
        return f"{self.type} - {self.status}"

    def cancel_document(self, reason: str) -> None:
        self.status = "canceled"
        self.content["cancel_reason"] = reason
        self.save()

    def approve_section(self, section_name: str, user: User) -> bool:
        if self.status == "canceled":
            return False

        existing_approval = DocumentApproval.objects.filter(
            document=self, section_name=section_name
        ).first()
        if existing_approval:
            return False

        DocumentApproval.objects.create(
            document=self, section_name=section_name, approved_by=user
        )
        return self.check_approvals()

    def reject_section(self, section_name: str, user: User) -> None:
        self.status = "canceled"
        DocumentApproval.objects.create(
            document=self,
            section_name=section_name,
            approved_by=user,
            approved=False,
            canceled=True,
        )
        self.save()

    def check_approvals(self) -> bool:
        if self.auto_mode:
            return True
        required_sections = self.required_sections.all().values_list("name", flat=True)
        approved_sections = self.approvals.filter(approved=True).values_list(
            "section_name", flat=True
        )
        if set(required_sections).issubset(set(approved_sections)):
            self.status = "approved_for_signing"
            self.save()
            return True
        return False
