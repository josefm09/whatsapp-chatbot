from django.db import models


class Appointment(models.Model):
    STATUS_CHOICES = [
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
    ]
    code = models.CharField(max_length=16, unique=True)
    user_phone = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=128)
    start_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="confirmed")

    def __str__(self):
        return f"{self.code} {self.user_phone} {self.start_at} {self.status}"
