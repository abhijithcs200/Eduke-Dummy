import csv
import datetime
import io
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from main.models import Institution, User, Classes, Students, Subjects
from django.db import transaction
from .forms import InstitutionForm, ClassesForm, ClassUploadForm, StudentForm,StudentUploadForm, SubjectUploadForm
from django.core.mail import send_mail
from django.conf import settings
import threading
import textwrap
import re
import pandas as pd
import openpyxl
from django.core.files.storage import FileSystemStorage
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import os
from datetime import datetime, date, timedelta

# Create your views here.

def security_checkup(request):
    return render(request, 'institution/security_checkup.html')

def institution_login(request):
    if request.method == 'POST':
        # Process login form data here
        email = request.POST.get('email')
        password = request.POST.get('password')

        # Authenticate institution (this is a placeholder, implement actual authentication)
        try:
            institution = Institution.objects.get(email=email, password=password)
            request.session['institution_id'] = institution.institution_id
            # Redirect to institution dashboard or homepage
            return redirect('institution:dashboard')
        except Institution.DoesNotExist:
            messages.error(request, 'Invalid credentials. Please try again.')
    return render(request, 'institution/login.html')

def institution_register(request):
    if request.method == 'POST':
        # Process registration form data here
        form = InstitutionForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, 'Institution registered successfully!', extra_tags='should_redirect')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = InstitutionForm()
    return render(request, 'institution/register.html', {'form': form})

def institution_dashboard(request):
    institution_id = request.session.get('institution_id')
    if not institution_id:
        return redirect('institution:login')
    institution = Institution.objects.get(institution_id=institution_id)
    
    total_classes = Classes.objects.filter(institution=institution).count()
    total_students = Students.objects.filter(class_obj__institution=institution).count()
    
    context = {
        'institution': institution,
        'total_classes': total_classes,
        'total_students': total_students,
    }
    return render(request, 'institution/dashboard.html', context)


def institution_profile(request):
    institution_id = request.session.get('institution_id')
    if not institution_id:
        return redirect('institution:login')
    institution = Institution.objects.get(institution_id=institution_id)

    if request.method == 'POST':
        form = InstitutionForm(request.POST, instance=institution)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('institution:profile')
        else:
            pass
    else:
        form = InstitutionForm(instance=institution)

    context = {
        'form': form,
        'institution': institution
    }
    return render(request, 'institution/profile.html', context)


def institution_classes(request):
    institution_id = request.session.get('institution_id')
    if not institution_id:
        messages.error(request, 'Please log in to access this page.')
        return redirect('login')

    try:
        institution = Institution.objects.get(institution_id=institution_id)
    except Institution.DoesNotExist:
        messages.error(request, "Institution not found.")
        return redirect('login')

    classes_list = Classes.objects.filter(institution=institution)
    
    if request.method == 'POST':
        # --- PATH A: BULK UPLOAD ---
        if 'bulk_upload' in request.POST:
            # Note: Ensure you have ClassUploadForm defined in forms.py
            upload_form = ClassUploadForm(request.POST, request.FILES)
            if upload_form.is_valid():
                file = request.FILES['file']
                fs = FileSystemStorage()
                filename = fs.save(file.name, file)
                file_path = fs.path(filename)

                try:
                    # Read Excel or CSV
                    if filename.endswith('.csv'):
                        df = pd.read_csv(file_path)
                    else:
                        df = pd.read_excel(file_path)

                    required_columns = ['Class Name', 'Class Head', 'Email', 'Password']
                    
                    # 1. Check Column Structure
                    if not all(col in df.columns for col in required_columns):
                        messages.error(request, "❌ Invalid file format! Missing required columns.")
                        return redirect('institution:classes')

                    error_list = []
                    success_count = 0
                    seen_emails = set() # To track duplicates within the file itself

                    with transaction.atomic():
                        for index, row in df.iterrows():
                            row_num = index + 2  # Adjust for 0-indexing and header row
                            
                            # Extract data and strip whitespace
                            c_name = str(row['Class Name']).strip()
                            c_head = str(row['Class Head']).strip()
                            c_email = str(row['Email']).strip()
                            c_pass = str(row['Password']).strip()

                            # 2. Check for Empty Fields
                            if any(val in ['nan', '', 'None'] for val in [c_name, c_head, c_email, c_pass]):
                                error_list.append(f"Row {row_num}: Missing required data.")
                                continue
                            password_regex = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{6,}$'

                            if not re.match(password_regex, c_pass):
                                error_list.append(
                                    f"Row {row_num}: Password for {c_email} is too weak. "
                                    "Must be 6+ chars with uppercase, lowercase, number, and special char."
                                )
                                continue

                            # 3. Validate Email Format
                            try:
                                validate_email(c_email)
                            except ValidationError:
                                error_list.append(f"Row {row_num}: Invalid email format ({c_email}).")
                                continue

                            # 4. Check Duplicate in File
                            if c_email in seen_emails:
                                error_list.append(f"Row {row_num}: Duplicate email in file ({c_email}).")
                                continue
                            seen_emails.add(c_email)

                            # 5. Check Duplicate in Database
                            if Classes.objects.filter(email=c_email).exists():
                                error_list.append(f"Row {row_num}: Email already registered in system ({c_email}).")
                                continue

                            # 6. Check Duplicate Class Name for this Institution
                            if Classes.objects.filter(class_name=c_name, institution=institution).exists():
                                error_list.append(f"Row {row_num}: Class name '{c_name}' already exists for your institution.")
                                continue

                            # If all checks pass, Create the records
                            try:
                                user_auth = User.objects.create(role='class_head')
                                Classes.objects.create(
                                    institution=institution,
                                    class_name=c_name,
                                    class_head=c_head,
                                    email=c_email,
                                    password=c_pass,
                                    user=user_auth
                                )
                                send_account_creation_email(
                                    c_email, c_pass, "class_head", c_head, institution.email
                                )
                                success_count += 1
                            except Exception as inner_e:
                                error_list.append(f"Row {row_num}: Database error - {str(inner_e)}")

                    # Report Summary
                    if success_count > 0:
                        messages.success(request, f"✅ {success_count} classes uploaded successfully!")
                    
                    if error_list:
                        # Joining errors with a break tag for display
                        error_msg = "⚠️ Errors found:<br>" + "<br>".join(error_list)
                        messages.error(request, error_msg)

                except Exception as e:
                    messages.error(request, f"❌ System Error: {str(e)}")
                finally:
                    fs.delete(filename)
                
                return redirect('institution:classes')

        # --- PATH B: MANUAL ENTRY ---
        else:
            form = ClassesForm(request.POST)
            if form.is_valid():
                data = form.cleaned_data
                if Classes.objects.filter(class_name=data['class_name'], institution=institution).exists():
                    messages.error(request, "This class name already exists.")
                else:
                    try:
                        with transaction.atomic():
                            user_record = User.objects.create(role='class_head')
                            new_class = form.save(commit=False)
                            new_class.user = user_record
                            new_class.institution = institution
                            new_class.save()
                            
                            # Send Email for manual entry
                            send_account_creation_email(
                                data['email'], 
                                data['password'], 
                                "class_head", 
                                data['class_head'], 
                                institution.email
                            )

                            messages.success(request, 'New class added and email sent!')
                            return redirect('institution:classes')
                    except Exception as e:
                        messages.error(request, f"Database error: {e}")
            else:
                messages.error(request, "Please correct the manual entry errors.")

    else:
        form = ClassesForm()

    context = {
        'institution': institution,
        'classes': classes_list,
        'form': form,
    }
    return render(request, 'institution/classes.html', context)

class EmailThread(threading.Thread):
    def __init__(self, subject, message, recipient_list, html_message=None):
        self.subject = subject
        self.message = message
        self.recipient_list = recipient_list
        self.html_message = html_message  # Add this to store the HTML version
        threading.Thread.__init__(self)

    def run(self):
        try:
            send_mail(
                subject=self.subject,
                message=self.message,  # Plain text version
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=self.recipient_list,
                fail_silently=False,
                html_message=self.html_message,  # Pass the HTML here
            )
            print(f"🟢 Thread: Email sent successfully to {self.recipient_list}")
        except Exception as e:
            print(f"🔴 Thread Error: {e}")

def send_account_creation_email(user_email, password, role, name, institution_email, user_id=None):
    subject = 'Welcome to Eduke App - Account Created Successfully'
    readable_role = role.replace('_', ' ').title()
    
    # Use user_id if provided (e.g., roll number for students), otherwise use email
    display_user_id = user_id if user_id else user_email

    # Plain-text version for email previews or non-HTML clients
    text_content = f"Hello {name}, your Eduke App account has been created successfully. Role: {readable_role}, User ID: {display_user_id}, Email: {user_email}, Password: {password}"

    # Styled HTML version - Centered card with purple accents
    html_content = f"""
    <div style="background-color: #f8fafc; padding: 20px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
        <div style="max-width: 500px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 16px; background-color: #ffffff;">
            
            <div style="text-align: center; margin-bottom: 20px;">
                <h2 style="color: #7c3aed; margin-bottom: 5px;">Account Created</h2>
                <p style="font-size: 14px; color: #64748b; text-transform: uppercase; letter-spacing: 1px;">Welcome to Eduke App</p>
            </div>
            
            <p style="color: #1e293b; line-height: 1.5;">Hello <strong>{name}</strong>,</p>
            <p style="color: #475569; line-height: 1.5;">We are pleased to inform you that your account has been created successfully! Please find your access details below.</p>
            
            <div style="background: #f5f3ff; padding: 25px; text-align: left; border-radius: 12px; margin: 25px 0; border: 1px dashed #c084fc;">
                <p style="margin: 5px 0; color: #1e293b;"><strong>Role:</strong> {readable_role}</p>
                <p style="margin: 5px 0; color: #1e293b;"><strong>User ID:</strong> <span style="font-family: monospace; font-weight: bold; color: #7c3aed;">{display_user_id}</span></p>
                <p style="margin: 5px 0; color: #1e293b;"><strong>Temporary Password:</strong> <span style="font-family: monospace; font-weight: bold; color: #7c3aed;">{password}</span></p>
            </div>
            
            <p style="color: #475569; font-size: 14px; line-height: 1.5;">
                For security reasons, we <strong>strongly recommend</strong> that you change your password immediately after your first login.
            </p>
            
            <div style="text-align: center; margin-top: 25px;">
                <a href="https://edukeapp.com/login" style="background-color: #7c3aed; color: #ffffff; padding: 12px 25px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">Login to Your Account</a>
            </div>
            
            <p style="font-size: 12px; color: #94a3b8; text-align: center; margin-top: 25px; border-top: 1px solid #f1f5f9; padding-top: 20px;">
                If you have any questions, please contact your institution at:<br>
                <a href="mailto:{institution_email}" style="color: #7c3aed; text-decoration: none; font-weight: bold;">{institution_email}</a>
            </p>
        </div>
    </div>
    """

    # Launch the thread
    # Note: We pass html_content as a keyword argument if your class supports it
    EmailThread(
        subject=subject, 
        message=text_content, 
        recipient_list=[user_email], 
        html_message=html_content
    ).start()
    
    return True


def edit_class(request, class_id):
    if request.method == 'POST':
        try:
            # 1. Attempt to find the record
            # We don't use get_object_or_404 here to avoid the 404 page
            try:
                class_instance = Classes.objects.get(id=class_id)
            except Classes.DoesNotExist:
                messages.error(request, "ACCESS DENIED: The record you are trying to edit does not exist in the database.")
                return redirect('institution:classes')

            # 2. Extract data from the POST request
            name = request.POST.get('class_name')
            head = request.POST.get('class_head')
            password = request.POST.get('password')
            email = request.POST.get('email')

            # 3. Update the instance fields
            class_instance.class_name = name
            class_instance.class_head = head
            class_instance.email = email
            
            # 4. Save password as plain text (as requested)
            if password:
                class_instance.password = password

            # 5. Commit changes to the database
            class_instance.save()

            # 6. Trigger your Success Toast
            messages.success(request, f"SYNC COMPLETE: {name} profile has been updated successfully.")
            
        except Exception as e:
            # 7. Catch any other database or system errors
            messages.error(request, f"SYSTEM OVERLOAD: An unexpected error occurred: {str(e)}")

    # 8. Redirect back to the main list
    return redirect('institution:classes')

def confrim_delete(request, class_id):
    try:
        class_instance = Classes.objects.get(id=class_id)
        name = class_instance.class_name
        class_instance.delete()
        messages.success(request, f'{name} deleted Successfully')
    except Classes.DoesNotExist:
        messages.error(request, 'Access Denied : The record try to delete is not found')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
    
    return redirect('institution:classes')

def class_details(request, class_id):
    institution_id = request.session.get('institution_id')
    if not institution_id:
        messages.error(request, 'Please log in to access this page.')
        return redirect('login')

    try:
        institution = Institution.objects.get(institution_id=institution_id)
    except Institution.DoesNotExist:
        messages.error(request, "Institution not found.")
        return redirect('login')

    try:
        data = Classes.objects.get(id=class_id)
        
        # Get students enrolled in this class
        from main.models import Students
        students = Students.objects.filter(class_obj=data)
        
        context={
            'class_obj':data,
            'students': students.order_by('roll_no'),
            'institution': institution,
        }
        
        return render(request, 'institution/class_detail.html', context)
    except Classes.DoesNotExist:
         messages.error(request, 'Access Denied : The record try to delete is not found')
         return redirect('institution:classes')
    except Exception as e:
        messages.error(request, "An unexpected error occurred.")
        print(f"Error: {e}") # For server-side debugging
        return redirect('institution:classess')
    # Ensure correct imports

def get_next_roll_no(request):
    class_id = request.GET.get('class_id')
    if not class_id:
        return JsonResponse({'next_roll': ''})

    try:
        class_obj = Classes.objects.get(id=class_id)
    except Classes.DoesNotExist:
        return JsonResponse({'next_roll': ''})

    class_name_lower = class_obj.class_name.lower().strip()
    
    # 1. Get Department Prefix Mappings from database only
    from main.models import ClassNameMapping
    institution_id = request.session.get('institution_id')
    mappings = {}
    
    if institution_id:
        # Get institution-specific mappings
        mappings_from_db = ClassNameMapping.objects.filter(institution_id=institution_id)
        for mapping in mappings_from_db:
            # Convert comma-separated keywords to tuple
            keywords = tuple(k.strip().lower() for k in mapping.class_name_keywords.split(','))
            mappings[keywords] = mapping.abbreviation
    
    # Find prefix using only database mappings
    prefix = None
    for keywords, p in mappings.items():
        if any(key in class_name_lower for key in keywords):
            prefix = p
            break
    
    # Determine if the mapping was found in database mappings
    mapping_found = bool(prefix)  # Check if a mapping was found from database
    mapping_type = 'database' if mapping_found else 'none'
    
    # If no mapping is found, return special message
    if not prefix:
        return JsonResponse({'next_roll': 'no roll found', 'mapping_found': False, 'mapping_type': 'none'})
    
    # 2. Extract Section (A or B) using Regex
    # Matches 'a' or 'b' as a standalone word (e.g., "MCA A" or "MCA-A")
    section_match = re.search(r'\b([ab])\b', class_name_lower)
    section = section_match.group(1).upper() if section_match else ''

    # 3. Construct Base Pattern
    year = str(date.today().year)[2:]
    base_pattern = f"{institution_id}S{prefix}{year}{section}" # e.g., 101SMCA26a or 101SCS26

    # 4. Find the latest student and increment
    latest_student = Students.objects.filter(
        class_obj_id=class_id, 
        roll_no__startswith=base_pattern
    ).order_by('-roll_no').first()

    if latest_student:
        try:
            # Extract only the numeric part after the base pattern
            suffix_str = latest_student.roll_no[len(base_pattern):]
            current_suffix = int(suffix_str)
            new_suffix = str(current_suffix + 1).zfill(3)
            next_roll = f"{base_pattern}{new_suffix}"
        except (ValueError, IndexError):
            next_roll = f"{base_pattern}001"
    else:
        next_roll = f"{base_pattern}001"
        
    print(f"New Roll no : {next_roll}")
    return JsonResponse({'next_roll': next_roll, 'mapping_found': mapping_found, 'mapping_type': mapping_type})

def institution_student(request):
    # 1. Fetch institution from session
    inst_id = request.session.get('institution_id')
    
    if not inst_id:
        messages.error(request, "Session expired. Please log in again.")
        return redirect('login')

    try:
        institution = Institution.objects.get(institution_id=inst_id)
    except Institution.DoesNotExist:
        messages.error(request, "Institution not found.")
        return redirect('login')

    # 2. Handle Search Query
    search_query = request.GET.get('search', '')
    students = Students.objects.filter(class_obj__institution=institution)
    
    if search_query:
        students = students.filter(first_name__icontains=search_query) | \
                   students.filter(last_name__icontains=search_query) | \
                   students.filter(roll_no__icontains=search_query)

    class_data = Classes.objects.filter(institution=institution)
    
    # 3. Handle POST Requests
    if request.method == 'POST':
        # --- PATH A: BULK UPLOAD ---
        if 'bulk_upload' in request.POST:
            upload_form = StudentUploadForm(request.POST, request.FILES)
            if upload_form.is_valid():
                file = request.FILES['file']
                
                # Check file extension
                filename = file.name
                if not (filename.endswith('.csv') or filename.endswith('.xlsx') or filename.endswith('.json')):
                    messages.error(request, "❌ Invalid file format! Please upload CSV, XLSX, or JSON file.")
                    return redirect('institution:manage_student')
                
                # Save file temporarily
                fs = FileSystemStorage()
                saved_filename = fs.save(filename, file)
                file_path = fs.path(saved_filename)
                
                try:
                    # Read file based on extension
                    if filename.endswith('.csv'):
                        df = pd.read_csv(file_path)
                    elif filename.endswith('.json'):
                        df = pd.read_json(file_path)
                    else:  # .xlsx
                        df = pd.read_excel(file_path)
                    
                    # Required columns for student import
                    required_columns = ['First Name', 'Last Name', 'Email', 'Roll No', 'Password', 'Class Name']
                    
                    # 1. Check Column Structure
                    if not all(col in df.columns for col in required_columns):
                        messages.error(request, f"❌ Invalid file format! Missing required columns: {', '.join(required_columns)}")
                        fs.delete(saved_filename)
                        return redirect('institution:manage_student')
                    
                    error_list = []
                    success_count = 0
                    seen_roll_nos = set()  # Track duplicates within file
                    seen_emails = set()    # Track duplicate emails within file
                    
                    with transaction.atomic():
                        for index, row in df.iterrows():
                            row_num = index + 2  # Adjust for 0-indexing and header row
                            
                            # Extract data and strip whitespace
                            roll_no = str(row['Roll No']).strip()
                            first_name = str(row['First Name']).strip()
                            last_name = str(row['Last Name']).strip()  # Required field
                            email = str(row['Email']).strip()
                            password = str(row['Password']).strip()
                            class_name = str(row['Class Name']).strip()  # Get class name instead of ID
                            
                            # 2. Check for Empty Required Fields
                            if any(val in ['nan', '', 'None'] for val in [roll_no, first_name, last_name, email, password, class_name]):
                                error_list.append(f"Row {row_num}: Missing required data (Roll No, First Name, Last Name, Email, Password, or Class Name).")
                                continue
                            
                            # 3. Validate Password Format
                            password_regex = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{6,}$'
                            if not re.match(password_regex, password):
                                error_list.append(
                                    f"Row {row_num}: Password for {email} is too weak. "
                                    "Must be 6+ chars with uppercase, lowercase, number, and special char."
                                )
                                continue
                            
                            # 4. Validate Email Format
                            try:
                                validate_email(email)
                            except ValidationError:
                                error_list.append(f"Row {row_num}: Invalid email format ({email}).")
                                continue
                            
                            # 5. Check Duplicate Roll Number in File
                            if roll_no in seen_roll_nos:
                                error_list.append(f"Row {row_num}: Duplicate roll number in file ({roll_no}).")
                                continue
                            seen_roll_nos.add(roll_no)
                            
                            # 6. Check Duplicate Email in File
                            if email in seen_emails:
                                error_list.append(f"Row {row_num}: Duplicate email in file ({email}).")
                                continue
                            seen_emails.add(email)
                            
                            # 7. Check Duplicate Roll Number in Database
                            if Students.objects.filter(roll_no=roll_no).exists():
                                error_list.append(f"Row {row_num}: Roll number already exists in system ({roll_no}).")
                                continue
                            
                            # 8. Check Duplicate Email in Database
                            if Students.objects.filter(email=email).exists():
                                error_list.append(f"Row {row_num}: Email already registered in system ({email}).")
                                continue
                            
                            # 9. Validate Class Name and Get Class Object
                            class_obj = None
                            try:
                                # Look up class by name for this institution
                                class_obj = Classes.objects.get(class_name=class_name, institution=institution)
                            except Classes.DoesNotExist:
                                error_list.append(f"Row {row_num}: Class '{class_name}' not found for your institution.")
                                continue
                            except Classes.MultipleObjectsReturned:
                                error_list.append(f"Row {row_num}: Multiple classes found with name '{class_name}'. Please ensure unique class names.")
                                continue
                            
                            # If all checks pass, create the student record
                            try:
                                user_auth = User.objects.create(role='student')
                                Students.objects.create(
                                    user=user_auth,
                                    roll_no=roll_no,
                                    first_name=first_name,
                                    last_name=last_name,
                                    email=email,
                                    password=password,  # Store as plain text as per your implementation
                                    class_obj=class_obj
                                )
                                
                                # Send account creation email
                                send_account_creation_email(
                                    email, 
                                    password, 
                                    "student", 
                                    first_name, 
                                    institution.email,
                                    roll_no
                                )
                                
                                success_count += 1
                            except Exception as inner_e:
                                error_list.append(f"Row {row_num}: Database error - {str(inner_e)}")
                    
                    # Report Summary
                    if success_count > 0:
                        messages.success(request, f"✅ {success_count} students uploaded successfully!")
                    
                    if error_list:
                        # Limit error display to first 10 errors to avoid overwhelming the UI
                        display_errors = error_list[:10]
                        error_msg = "⚠️ Errors found:<br>" + "<br>".join(display_errors)
                        if len(error_list) > 10:
                            error_msg += f"<br>... and {len(error_list) - 10} more errors."
                        messages.error(request, error_msg)
                    
                except Exception as e:
                    messages.error(request, f"❌ System Error: {str(e)}")
                finally:
                    # Clean up temporary file
                    fs.delete(saved_filename)
                
                return redirect('institution:manage_student')
            else:
                messages.error(request, "Please correct the bulk upload form errors.")

        # --- PATH B: MANUAL SINGLE ENTRY ---
        else:
            form = StudentForm(request.POST, institution=institution)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        user_auth = User.objects.create(role='student')
                        student = form.save(commit=False)
                        student.user = user_auth
                        student.save()
                        
                        # Send account creation email
                        send_account_creation_email(
                            student.email,
                            student.password,
                            "student",
                            student.first_name,
                            institution.email,
                            student.roll_no
                        )
                        
                    messages.success(request, f"✅ Student {student.first_name} registered successfully.")
                    return redirect('institution:manage_student')
                except Exception as e:
                    messages.error(request, f"❌ Error: {str(e)}")
            else:
                messages.error(request, "Please correct the manual entry errors.")
    else:
        form = StudentForm(institution=institution)

    return render(request, 'institution/manage_student.html', {
        'form': form,
        'institution': institution,
        'students': students.order_by('class_obj__class_name', 'roll_no'), 
        'search_query': search_query,
        'classes': class_data
    })
    

def delete_student(request, student_id):
    if request.method == 'POST':
        try:
            # Get the student instance
            student = Students.objects.get(id=student_id)
            student_name = f"{student.first_name} {student.last_name}"
            
            # Get the associated user and delete both
            user = student.user
            student.delete()
            if user:
                user.delete()
            
            messages.success(request, f"✅ Student {student_name} has been deleted successfully.")
        except Students.DoesNotExist:
            messages.error(request, "❌ Student not found.")
        except Exception as e:
            messages.error(request, f"❌ Error deleting student: {str(e)}")
    
    return redirect('institution:manage_student')

def edit_student(request, student_id):
    """
    Edit student information with validation
    """
    if request.method == 'POST':
        try:
            # Get the student instance
            student = Students.objects.get(id=student_id)
            
            # Get form data
            roll_no = request.POST.get('roll_no', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '').strip()
            class_id = request.POST.get('class_obj')
            
            # Validate required fields
            if not all([roll_no, first_name, last_name, email, class_id]):
                messages.error(request, "❌ All fields except password are required.")
                return redirect('institution:manage_student')
            
            # Validate email format
            try:
                validate_email(email)
            except ValidationError:
                messages.error(request, f"❌ Invalid email format: {email}")
                return redirect('institution:manage_student')

            # Check if roll number is changed and already exists for another student
            if roll_no != student.roll_no:
                if Students.objects.filter(roll_no=roll_no).exclude(id=student_id).exists():
                    messages.error(request, f"❌ Roll number {roll_no} is already taken by another student.")
                    return redirect('institution:manage_student')

            # Check if email is changed and already exists for another student
            if email != student.email:
                if Students.objects.filter(email=email).exclude(id=student_id).exists():
                    messages.error(request, f"❌ Email {email} is already registered for another student.")
                    return redirect('institution:manage_student')
            
            # Validate password if provided
            if password:
                password_regex = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{6,}$'
                if not re.match(password_regex, password):
                    messages.error(request, "❌ Password must be 6+ characters with uppercase, lowercase, number, and special character.")
                    return redirect('institution:manage_student')
            
            # Get class object
            try:
                class_obj = Classes.objects.get(id=class_id)
            except Classes.DoesNotExist:
                messages.error(request, "❌ Selected class not found.")
                return redirect('institution:manage_student')
            
            # Update student information
            student.roll_no = roll_no
            student.first_name = first_name
            student.last_name = last_name
            student.email = email
            student.class_obj = class_obj
            
            # Update password only if provided
            if password:
                student.password = password
            
            student.save()
            
            messages.success(request, f"✅ Student {first_name} {last_name} has been updated successfully.")
            
        except Students.DoesNotExist:
            messages.error(request, "❌ Student not found.")
        except Exception as e:
            messages.error(request, f"❌ Error updating student: {str(e)}")
    
    return redirect('institution:manage_student')
    

def institution_subjects(request):
    institution_id = request.session.get('institution_id')
    if not institution_id:
        messages.error(request, 'Please log in to access this page.')
        return redirect('login')

    try:
        institution = Institution.objects.get(institution_id=institution_id)
    except Institution.DoesNotExist:
        messages.error(request, "Institution not found.")
        return redirect('login')

    subjects = Subjects.objects.filter(class_obj__institution=institution)

    # Get all classes for the institution (for the dropdown)
    classes_list = Classes.objects.filter(institution=institution)
    
    if request.method == 'POST':
        # --- PATH A: BULK UPLOAD ---
        if 'bulk_upload' in request.POST:
            upload_form = SubjectUploadForm(request.POST, request.FILES)
            if upload_form.is_valid():
                file = request.FILES['file']
                
                # Check file extension
                filename = file.name
                if not (filename.endswith('.csv') or filename.endswith('.xlsx') or filename.endswith('.json')):
                    messages.error(request, "❌ Invalid file format! Please upload CSV, XLSX, or JSON file.")
                    return redirect('institution:manage_student')
            
            # Save file temporarily
            fs = FileSystemStorage()
            saved_filename = fs.save(filename, file)
            file_path = fs.path(saved_filename)
            
            try:
                # Read file based on extension
                if filename.endswith('.csv'):
                    df = pd.read_csv(file_path)
                else:  # .xlsx
                    df = pd.read_excel(file_path)
                
                # Required columns for subject import
                required_columns = ['Subject Name', 'Subject Head', 'Email', 'Password', 'Class Name']
                
                # 1. Check Column Structure
                if not all(col in df.columns for col in required_columns):
                    messages.error(request, f"❌ Invalid file format! Missing required columns: {', '.join(required_columns)}")
                    fs.delete(saved_filename)
                    return redirect('institution:subjects')
                
                error_list = []
                success_count = 0
                seen_emails = set()  # Track duplicate emails within file
                
                with transaction.atomic():
                    for index, row in df.iterrows():
                        row_num = index + 2  # Adjust for 0-indexing and header row
                        
                        # Extract data and strip whitespace
                        subject_name = str(row['Subject Name']).strip()
                        subject_head = str(row['Subject Head']).strip()
                        email = str(row['Email']).strip()
                        password = str(row['Password']).strip()
                        class_name = str(row['Class Name']).strip()  # Get class name instead of ID
                        
                        # 2. Check for Empty Required Fields
                        if any(val in ['nan', '', 'None'] for val in [subject_name, subject_head, email, password, class_name]):
                            error_list.append(f"Row {row_num}: Missing required data (Subject Name, Subject Head, Email, Password, or Class Name).")
                            continue
                        
                        # 3. Validate Password Format
                        password_regex = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{6,}$'
                        if not re.match(password_regex, password):
                            error_list.append(
                                f"Row {row_num}: Password for {email} is too weak. "
                                "Must be 6+ chars with uppercase, lowercase, number, and special char."
                            )
                            continue
                        
                        # 4. Validate Email Format
                        try:
                            validate_email(email)
                        except ValidationError:
                            error_list.append(f"Row {row_num}: Invalid email format ({email}).")
                            continue
                        
                        # 5. Check Duplicate Email in File
                        if email in seen_emails:
                            error_list.append(f"Row {row_num}: Duplicate email in file ({email}).")
                            continue
                        seen_emails.add(email)
                        
                        # 6. Check Duplicate Email in Database
                        if Subjects.objects.filter(email=email).exists():
                            error_list.append(f"Row {row_num}: Email already registered in system ({email}).")
                            continue
                        
                        # 7. Validate Class Name and Get Class Object
                        class_obj = None
                        try:
                            # Look up class by name for this institution
                            class_obj = Classes.objects.get(class_name=class_name, institution=institution)
                        except Classes.DoesNotExist:
                            error_list.append(f"Row {row_num}: Class '{class_name}' not found for your institution.")
                            continue
                        except Classes.MultipleObjectsReturned:
                            error_list.append(f"Row {row_num}: Multiple classes found with name '{class_name}'. Please ensure unique class names.")
                            continue
                        
                        # If all checks pass, create the subject record
                        try:
                            user_auth = User.objects.create(role='subject_head')
                            Subjects.objects.create(
                                subject_name=subject_name,
                                subject_head=subject_head,
                                email=email,
                                password=password,  # Store as plain text as per your implementation
                                class_obj=class_obj,
                                institution=institution,
                                user=user_auth
                            )
                            
                            # Send account creation email
                            send_account_creation_email(
                                email, 
                                password, 
                                "subject_head", 
                                subject_head, 
                                institution.email
                            )
                            
                            success_count += 1
                        except Exception as inner_e:
                            error_list.append(f"Row {row_num}: Database error - {str(inner_e)}")
                
                # Report Summary
                if success_count > 0:
                    messages.success(request, f"✅ {success_count} subjects uploaded successfully!")
                
                if error_list:
                    # Limit error display to first 10 errors to avoid overwhelming the UI
                    display_errors = error_list[:10]
                    error_msg = "⚠️ Errors found:<br>" + "<br>".join(display_errors)
                    if len(error_list) > 10:
                        error_msg += f"<br>... and {len(error_list) - 10} more errors."
                    messages.error(request, error_msg)
                
            except Exception as e:
                messages.error(request, f"❌ System Error: {str(e)}")
            finally:
                # Clean up temporary file
                fs.delete(saved_filename)
            
            return redirect('institution:subjects')

        # --- PATH B: MANUAL ENTRY ---
        else:
            form = SubjectForm(request.POST, institution=institution)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        user_auth = User.objects.create(role='subject_head')
                        subject = form.save(commit=False)
                        subject.user = user_auth
                        subject.institution = institution
                        subject.save()
                        
                        # Send account creation email
                        send_account_creation_email(
                            subject.email,
                            subject.password,
                            "subject_head",
                            subject.subject_head,
                            institution.email
                        )
                        
                    messages.success(request, f"✅ Subject {subject.subject_name} registered successfully.")
                    return redirect('institution:subjects')
                except Exception as e:
                    messages.error(request, f"❌ Error: {str(e)}")
            else:
                messages.error(request, "Please correct the form errors.")
    else:
        from .forms import SubjectForm
        form = SubjectForm(institution=institution)

    context = {
        'institution': institution,
        'subjects': subjects.order_by('id'),
        'classes': classes_list,
        'form': form,
    }
    return render(request, 'institution/subjects.html', context)


def edit_subject(request, subject_id):
    """
    Edit subject information with validation
    """
    if request.method == 'POST':
        try:
            # Get the subject instance
            subject = Subjects.objects.get(id=subject_id)
            
            # Get form data
            subject_name = request.POST.get('subject_name', '').strip()
            subject_head = request.POST.get('subject_head', '').strip()
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '').strip()
            class_id = request.POST.get('class_obj')
            
            # Validate required fields
            if not all([subject_name, subject_head, email, class_id]):
                messages.error(request, "❌ All fields except password are required.")
                return redirect('institution:subjects')
            
            # Validate email format
            try:
                validate_email(email)
            except ValidationError:
                messages.error(request, f"❌ Invalid email format: {email}")
                return redirect('institution:subjects')

            # Check if email is changed and already exists for another subject
            if email != subject.email:
                if Subjects.objects.filter(email=email).exclude(id=subject_id).exists():
                    messages.error(request, f"❌ Email {email} is already registered for another subject.")
                    return redirect('institution:subjects')
            
            # Validate password if provided
            if password:
                password_regex = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{6,}$'
                if not re.match(password_regex, password):
                    messages.error(request, "❌ Password must be 6+ characters with uppercase, lowercase, number, and special character.")
                    return redirect('institution:subjects')
            
            # Get class object
            try:
                class_obj = Classes.objects.get(id=class_id)
            except Classes.DoesNotExist:
                messages.error(request, "❌ Selected class not found.")
                return redirect('institution:subjects')
            
            # Update subject information
            subject.subject_name = subject_name
            subject.subject_head = subject_head
            subject.email = email
            subject.class_obj = class_obj
            
            # Update password only if provided
            if password:
                subject.password = password
            
            subject.save()
            
            messages.success(request, f"✅ Subject {subject_name} has been updated successfully.")
            
        except Subjects.DoesNotExist:
            messages.error(request, "❌ Subject not found.")
        except Exception as e:
            messages.error(request, f"❌ Error updating subject: {str(e)}")
    
    return redirect('institution:subjects')





def delete_subject(request, subject_id):
    if request.method == 'POST':
        try:
            # Get the subject instance
            subject = Subjects.objects.get(id=subject_id)
            subject_name = subject.subject_name
            
            # Get the associated user and delete both
            user = subject.user
            subject.delete()
            if user:
                user.delete()
            
            messages.success(request, f"✅ Subject {subject_name} has been deleted successfully.")
        except Subjects.DoesNotExist:
            messages.error(request, "❌ Subject not found.")
        except Exception as e:
            messages.error(request, f"❌ Error deleting subject: {str(e)}")
    
    return redirect('institution:subjects')


def update_class_name_mappings(request):
    if request.method == 'POST':
        from main.models import ClassNameMapping
        import json
        institution_id = request.session.get('institution_id')
        
        if not institution_id:
            return JsonResponse({'success': False, 'error': 'Institution not found'})
        
        try:
            # Get the institution object
            institution = Institution.objects.get(institution_id=institution_id)
            
            # Clear existing mappings for this institution
            ClassNameMapping.objects.filter(institution=institution).delete()
            
            # Get the new mappings from the request - handle both JSON and form data
            if request.content_type and 'application/json' in request.content_type:
                try:
                    body_unicode = request.body.decode('utf-8')
                    body_data = json.loads(body_unicode)
                    mappings_list = body_data.get('mappings', [])
                except json.JSONDecodeError:
                    return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
            else:
                # Handle form data (for backward compatibility)
                mappings_data = request.POST.get('mappings', '[]')
                mappings_list = json.loads(mappings_data)
            
            # Clear existing mappings for this institution
            ClassNameMapping.objects.filter(institution=institution).delete()
            
            # Create new mappings
            for mapping in mappings_list:
                keywords = mapping.get('keywords', '')
                abbreviation = mapping.get('abbreviation', '')
                
                if keywords and abbreviation:
                    ClassNameMapping.objects.create(
                        class_name_keywords=keywords,
                        abbreviation=abbreviation,
                        institution=institution
                    )
            
            return JsonResponse({'success': True})
            
        except Institution.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Institution not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    # For GET request, return the current mappings
    from main.models import ClassNameMapping
    institution_id = request.session.get('institution_id')
    
    if not institution_id:
        return JsonResponse({'success': False, 'error': 'Institution not found'})
    
    try:
        institution = Institution.objects.get(institution_id=institution_id)
        mappings = ClassNameMapping.objects.filter(institution=institution)
        
        mappings_list = []
        for mapping in mappings:
            mappings_list.append({
                'keywords': mapping.class_name_keywords,
                'abbreviation': mapping.abbreviation
            })
        
        return JsonResponse({'success': True, 'mappings': mappings_list})
        
    except Institution.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Institution not found'})


def get_missing_mappings(request):
    from main.models import ClassNameMapping, Classes, Institution
    institution_id = request.session.get('institution_id')
    
    if not institution_id:
        return JsonResponse({'success': False, 'error': 'Institution not found'})
    
    try:
        institution = Institution.objects.get(institution_id=institution_id)
        # Get all classes for this institution
        all_classes = Classes.objects.filter(institution=institution)
        # Get all mappings for this institution
        mappings = ClassNameMapping.objects.filter(institution=institution)
        
        # Create a flat list of all valid lowercase keywords
        all_keywords = []
        for m in mappings:
            # Splits "mca, master of computer" into ['mca', 'master of computer']
            keywords = [k.strip().lower() for k in m.class_name_keywords.split(',') if k.strip()]
            all_keywords.extend(keywords)
            
        missing_classes = []
        for cls in all_classes:
            name_lower = cls.class_name.lower().strip()
            # Check if any mapping keyword is contained within the class name
            has_mapping = any(kw in name_lower for kw in all_keywords)
            
            if not has_mapping:
                missing_classes.append({
                    'id': cls.id,
                    'name': cls.class_name
                })
        
        # Return success and the list (even if empty)
        return JsonResponse({
            'success': True, 
            'missing_classes': missing_classes,
            'is_fully_mapped': len(missing_classes) == 0
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})