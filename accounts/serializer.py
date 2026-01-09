from rest_framework import serializers
from .models import User

class SignUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'email',
            'first_name',
            'last_name',
            'password',
            'role', 
            'is_verified',
            'department',
            'contact_number'
        ]

        extra_kwargs = {
            'password' : {
                'write_only': True
            }
        }

    def validate_email(self, value):
        domain = value.split('@')[1]
        if domain not in ['ornatesolar.com', 'ornatesolar.in', 'ornateinroof.in', 'ornateinroof.com']:
            raise serializers.ValidationError("Only emails with ornatesolar.com or ornatesolar.in domain are allowed.")
        return value

    def create(self, validated_data):
        email = validated_data['email'].lower()
        first_name = validated_data['first_name'].lower()
        last_name = validated_data['last_name'].lower()
        role = validated_data['role']
        is_verified = validated_data['is_verified']
        department = validated_data['department']
        contact_number = validated_data['contact_number']

        # Create new User
        user = User.objects.create(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            is_verified=is_verified,
            department=department,
            contact_number=contact_number
        )
        password = validated_data['password']
        user.set_password(password)
        user.save()
        return user
    
class UserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model=User
        fields = [
            'email',
            'name',
        ]

    def get_name(self, obj):
        fname = obj.first_name.capitalize()
        lname = obj.last_name.capitalize()

        return fname + ' ' + lname
    
    