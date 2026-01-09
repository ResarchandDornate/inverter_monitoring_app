from .models import OTP

def generate_otp(email):
    try:
        existing_otp = OTP.objects.get(email=email)
        if existing_otp:
            existing_otp.delete()
    except Exception as e:
        print("OTP does not exist")
    
    otp_instance = OTP.create(email)
    otp_instance.save()
    print("OTP is", otp_instance.otp)
    return otp_instance

