from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import random

from django.contrib.auth.models import BaseUserManager

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        # Assigning the role of Admin
        extra_fields.setdefault('role', User.ADMIN)
        extra_fields.setdefault('is_verified', True)
        
        return self.create_user(email, password, **extra_fields)


# Create your models here.
class User(AbstractUser):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=False, blank=True, null=True)
    department = models.CharField(max_length=100, default="")
    contact_number = models.CharField(max_length=15, default="")
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    
    ADMIN = 'Admin'
    RFQ_FILLER = 'RFQFiller'
    ACCOUNTS_TEAM = 'AccountsTeam'
    ACCOUNTS_TEAM_MANAGER = 'AccountsTeamManager'
    MANAGER = 'Manager'
    SENIOR_MANAGER = 'SeniorManager'
    FINANCE = 'Finance'
    FINANCE_MANAGER = 'FinanceManager'
    FINANCE_SENIOR_MANAGER = 'FinanceSeniorManager'
    BOSFiller = 'BOSFiller'
    BOSManager = 'BOSManager' 
    
    ROLE_CHOICES = [
        (ADMIN, 'Admin'),
        (RFQ_FILLER, 'RFQFiller'),
        (ACCOUNTS_TEAM, 'AccountsTeam'),
        (MANAGER, 'Manager'),
        (SENIOR_MANAGER, 'SeniorManager'),
        (ACCOUNTS_TEAM_MANAGER, 'AccountsTeamManager'),
        (FINANCE, 'Finance'),
        (FINANCE_MANAGER, 'FinanceManager'),
        (FINANCE_SENIOR_MANAGER, 'FinanceSeniorManager'),
        (BOSFiller, 'BOSFiller'),
        (BOSManager, 'BOSManager')
    ]
    # Roles should have different model
    # Permission for a perticular user
    # permission and roles mapping
    # users and roles mapping 
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=RFQ_FILLER)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = [] 

    objects = CustomUserManager()

    def __str__(self):
        return self.email
    
class OTP(models.Model):
    email = models.EmailField(unique=True)
    otp = models.CharField(max_length=6)
    expiry_time = models.DateTimeField()

    @classmethod
    def create(cls, email):
        otp_instance = cls()
        otp_instance.email = email
        otp_instance.otp = str(random.randint(100000, 999999))
        otp_instance.expiry_time = timezone.now() + timezone.timedelta(minutes=5)
        return otp_instance

    def is_valid(self, user_otp):
        return self.otp == str(user_otp) and timezone.now() <= self.expiry_time