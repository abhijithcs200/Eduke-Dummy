from django.shortcuts import render, redirect
from django.contrib import messages
from main.models import Students


def student_login(request):
    if request.method == 'POST':
        roll_no = request.POST.get('roll_no').upper()
        password = request.POST.get('password')
        
        try:
            # Find student by roll number
            student = Students.objects.get(roll_no=roll_no)
            
            # Check if password matches (note: passwords are stored as plain text)
            if student.password == password:
                # Store student info in session
                request.session['student_id'] = student.id
                request.session['student_roll_no'] = student.roll_no
                request.session['student_name'] = f"{student.first_name} {student.last_name}"
                request.session['student_class'] = student.class_obj.class_name if student.class_obj else None
                
                messages.success(request, f'Welcome {student.first_name}! Login successful.')
                return redirect('student:dashboard')  # Redirect to student dashboard
            else:
                messages.error(request, 'Invalid password. Please try again.')
        except Students.DoesNotExist:
            messages.error(request, 'Invalid roll number. Please try again.')
    
    return render(request, 'student/login.html')

def dashboard(request):
    # Check if student is logged in
    if 'student_id' not in request.session:
        messages.error(request, 'Please log in to access the dashboard.')
        return redirect('student:login')
    
    # Get student info from session
    student_id = request.session['student_id']
    student = Students.objects.get(id=student_id)
    
    context = {
        'student': student,
    }
    return render(request, 'student/dashboard.html', context)

def profile(request):
    # Check if student is logged in
    if 'student_id' not in request.session:
        messages.error(request, 'Please log in to access your profile.')
        return redirect('student:login')
    
    # Get student info from session
    student_id = request.session['student_id']
    student = Students.objects.get(id=student_id)
    
    context = {
        'student': student,
    }
    return render(request, 'student/profile.html', context)
