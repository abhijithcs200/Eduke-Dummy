from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.core.cache import cache
from .models import Institution, Students
import threading
import textwrap
from django.core.mail import send_mail
from django.conf import settings

from django.views.decorators.csrf import csrf_exempt
import json

# Create your views here.

def index(request):
    return render(request, 'main/index.html')

@csrf_exempt
def contact_email(request):
    if request.method == 'POST':
        try:
            # Parse JSON data from the AJAX request
            data = json.loads(request.body)
            
            name = data.get('name', '')
            institution = data.get('institution', '')
            email = data.get('email', '')
            message = data.get('message', '')
            
            # Validate required fields
            if not name or not email or not message:
                return JsonResponse({'status': 'error', 'message': 'Required fields missing.'})

            subject = f'New Inquiry: {name} ({institution})'

            # Professional Plain Text Fallback
            plain_message = f"New Contact Submission\n\nName: {name}\nEmail: {email}\nInstitution: {institution}\n\nMessage:\n{message}"

            # Modern Card-Style HTML
            html_message = f"""
            <div style="background-color: #f8fafc; padding: 40px 10px; font-family: 'Segoe UI', Arial, sans-serif;">
                <div style="max-width: 600px; margin: auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                    <div style="background-color: #7c3aed; padding: 20px; text-align: center;">
                        <h2 style="color: #ffffff; margin: 0; font-size: 20px; font-weight: 600;">Eduke Web Inquiry</h2>
                    </div>
                    
                    <div style="padding: 30px;">
                        <div style="margin-bottom: 25px;">
                            <label style="color: #64748b; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">Sender Details</label>
                            <div style="margin-top: 8px; color: #1e293b;">
                                <p style="margin: 4px 0;"><strong>Name:</strong> {name}</p>
                                <p style="margin: 4px 0;"><strong>Email:</strong> <a href="mailto:{email}" style="color: #7c3aed; text-decoration: none;">{email}</a></p>
                                <p style="margin: 4px 0;"><strong>Institution:</strong> {institution}</p>
                            </div>
                        </div>

                        <div style="margin-bottom: 10px;">
                            <label style="color: #64748b; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">Message Body</label>
                            <div style="margin-top: 10px; padding: 20px; background-color: #f1f5f9; border-left: 4px solid #7c3aed; border-radius: 4px; color: #334155; line-height: 1.6;">
                                {message}
                            </div>
                        </div>
                    </div>

                    <div style="background-color: #f8fafc; padding: 15px; text-align: center; border-top: 1px solid #e2e8f0;">
                        <p style="font-size: 12px; color: #94a3b8; margin: 0;">This inquiry was sent via the Eduke Website Contact Form.</p>
                    </div>
                </div>
            </div>
            """
            
            try:
                send_mail(
                    subject=subject,
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,  # Use sender's email as from
                    recipient_list=[email],  # Use sender's email as recipient
                    html_message=html_message,
                    fail_silently=False
                )
                
                return JsonResponse({'status': 'success', 'message': 'Thank you for contacting us. We will get back to you soon!'})
            
            except Exception as e:
                print(f"Error sending email: {str(e)}")
                return JsonResponse({'status': 'error', 'message': 'Failed to send email. Please try again later.'})
                
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid request data.'})
        
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            return JsonResponse({'status': 'error', 'message': 'An unexpected error occurred.'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

def user_portal(request):
    return render(request, 'main/user_portal.html')

def logout(request):
    request.session.flush()
    return redirect('index')


# Helper to find which model owns the email
def get_user_by_email(email, user_type):
    mapping = {'institution': Institution, 'student': Students}
    model = mapping.get(user_type)
    if model:
        user = model.objects.filter(email=email).first()
        if user:
            return user, model
    return None, None

def forgot_password(request, user_type):
    if request.method == 'POST':
        email = request.POST.get('email')
        user, _ = get_user_by_email(email, user_type)
        print(user_type)
        
        if not user:
            return JsonResponse({'status': 'error', 'message': 'Email not found in our records.'})
        
        otp = generate_otp() # Your existing OTP generator
        print(f"Generated OTP: {otp} for email: {email}")
        cache.set(f"otp_{email}", otp, timeout=180)
        request.session['reset_email'] = email
        request.session['reset_user_type'] = user_type
        
        try:
            send_otp_via_email(email, otp)
            return JsonResponse({'status': 'success', 'message': 'OTP sent to your email.'})
        except Exception:
            return JsonResponse({'status': 'error', 'message': 'Failed to send email.'})
            
    return render(request, 'main/forgot_password.html', {'user_type': user_type})

def verify_otp(request, user_type):
    if request.method == 'POST':
        otp = request.POST.get('otp')
        email = request.session.get('reset_email')
        
        cached_otp = cache.get(f"otp_{email}")
        if cached_otp and str(cached_otp) == str(otp):
            # We set a 'verified' flag in session so they can proceed to reset
            request.session['otp_verified'] = True
            return JsonResponse({'status': 'success', 'message': 'OTP verified.'})
        
        return JsonResponse({'status': 'error', 'message': 'Invalid or expired OTP.'})

def reset_password(request, user_type):
    if request.method == 'POST':
        email = request.session.get('reset_email')
        is_verified = request.session.get('otp_verified')
        new_password = request.POST.get('new_password')
        
        if not email or not is_verified:
            return JsonResponse({'status': 'error', 'message': 'Session expired. Restart process.'})

        user, _ = get_user_by_email(email, user_type)
       
        if user:
            user.password = new_password  # Note: Use make_password(new_password) if using Django Auth
            user.save()
            
            # Cleanup session
            del request.session['reset_email']
            del request.session['otp_verified']
            return JsonResponse({'status': 'success', 'message': 'Password updated successfully!'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request.'})

def generate_otp():
    import random
    return random.randint(100000, 999999)

def send_otp_via_email(email, otp):
    print(f"Sending OTP: {otp} to {email}")
    def _send():
        subject = f"{otp} is your Secure Recovery Code"
        
        # Clean plain-text body (used if HTML fails or for notifications)
        message = textwrap.dedent(f"""
            Hello,

            We received a request to reset your password for your Eduke account. 
            Use the following verification token to proceed:

            Verification Token: {otp}

            This code is valid for 3 minutes. For your security, do not share this code with anyone.

            If you did not request this reset, please ignore this email.

            Securely,
            The Eduke Security Team
        """).strip()
        
        # Styled HTML version
        html_message = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 500px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 16px; background-color: #ffffff;">
            <div style="text-align: center; margin-bottom: 20px;">
                <h2 style="color: #7c3aed; margin-bottom: 5px;">Access Reset</h2>
                <p style="font-size: 14px; color: #64748b; text-transform: uppercase; letter-spacing: 1px;">Step 2: Authenticity Check</p>
            </div>
            
            <p style="color: #1e293b; line-height: 1.5;">Hello,</p>
            <p style="color: #475569; line-height: 1.5;">Use the verification token below to complete your password reset. This code is valid for <strong style="color: #7c3aed;">3 minutes</strong>.</p>
            
            <div style="background: #f5f3ff; padding: 30px; text-align: center; border-radius: 12px; margin: 25px 0; border: 1px dashed #c084fc;">
                <span style="font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #2e1065; font-family: monospace;">{otp}</span>
            </div>
            
            <p style="font-size: 12px; color: #94a3b8; text-align: center; margin-top: 25px;">
                If you did not request this reset, please ignore this email or contact security support.<br>
                <strong>Do not share this code with anyone.</strong>
            </p>
        </div>
        """

        try:
            send_mail(
                subject=subject,
                message=message,  # This is the "body"
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
                html_message=html_message
            )
            print(f"OTP email successfully dispatched to {email}")
        except Exception as e:
            print(f"Failed to send OTP email: {str(e)}")

    # Start the background thread
    threading.Thread(target=_send, daemon=True).start()
        