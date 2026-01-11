from main.models import Institution, Classes, Students, Subjects
from django import forms
import re

class InstitutionForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'input-field'
        }),
        max_length=191,
        help_text="Required: 6+ chars, 1 uppercase, 1 digit, 1 special char."
    )

    class Meta:
        model = Institution
        fields = ['institution_name', 'email', 'abbreviation', 'password']
        
        # Adding class names and placeholders to match your UI
        widgets = {
            'institution_name': forms.TextInput(attrs={
                'placeholder': 'Global University of Excellence',
                'class': 'input-field'
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'admin@edu.com',
                'class': 'input-field'
            }),
            'abbreviation': forms.TextInput(attrs={
                'placeholder': 'e.g. MIT, Stanford',
                'class': 'input-field'
            }),
        }
    
    def clean_password(self):
        password = self.cleaned_data.get('password')
        # You can add custom password validation here if needed

        if len(password) < 6:
            raise forms.ValidationError("Password must be at least 6 characters long.")
        if not re.search(r'[A-Z]', password):
            raise forms.ValidationError("Password must contain at least one uppercase letter.")
        if not re.search(r'[0-9]', password):
            raise forms.ValidationError("Password must contain at least one digit.")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise forms.ValidationError("Password must contain at least one special character.")
        if not re.search(r'[a-z]', password):
            raise forms.ValidationError("Password must contain at least one lowercase letter.")
        return password

    def save(self, commit=True):
        institution = super().save(commit=False)
            # Here you can hash the password before saving if needed
        if commit:
            institution.save()
        return institution
    
class ClassesForm(forms.ModelForm):
    # Overriding password field to add specific UI and constraints
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'input-field',
            'placeholder': '••••••••'
        }),
        max_length=191,
        help_text="Required: 6+ chars, 1 uppercase, 1 digit, 1 special char."
    )

    class Meta:
        model = Classes
        # Order of fields as they will appear in the HTML
        fields = ['class_name', 'class_head', 'email', 'password']
        
        # Adding styling classes and placeholders for the other fields
        widgets = {
            'class_name': forms.TextInput(attrs={
                'placeholder': 'e.g. MCA, MBA, etc.',
                'class': 'input-field'
            }),
            'class_head': forms.TextInput(attrs={
                'placeholder': 'e.g. Dr. John Smith',
                'class': 'input-field'
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'class-admin@edu.com',
                'class': 'input-field'
            }),
        }
    
    def clean_password(self):
        password = self.cleaned_data.get('password')

        if len(password) < 6:
            raise forms.ValidationError("Password must be at least 6 characters long.")
        if not re.search(r'[A-Z]', password):
            raise forms.ValidationError("Password must contain at least one uppercase letter.")
        if not re.search(r'[0-9]', password):
            raise forms.ValidationError("Password must contain at least one digit.")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise forms.ValidationError("Password must contain at least one special character.")
            
        return password

class ClassUploadForm(forms.Form):
    file = forms.FileField()

class StudentUploadForm(forms.Form):
    file = forms.FileField()
    
class SubjectUploadForm(forms.Form):
    file = forms.FileField()
    
class StudentForm(forms.ModelForm):
    # Explicitly defining the password field for UI and validation
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'input-field',
            'placeholder': '••••••••'
        }),
        help_text="Must be 6+ chars, 1 uppercase, 1 digit, 1 special char."
    )

    class Meta:
        model = Students
        # Includes first_name and last_name from your Students model
        fields = ['roll_no', 'first_name', 'last_name', 'email', 'class_obj', 'password']
        
        widgets = {
            'roll_no': forms.TextInput(attrs={'placeholder': 'Roll Number', 'class': 'input-field'}),
            'first_name': forms.TextInput(attrs={'placeholder': 'Enter First Name', 'class': 'input-field'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Enter Last Name', 'class': 'input-field'}),
            'email': forms.EmailInput(attrs={'placeholder': 'student@email.com', 'class': 'input-field'}),
            'class_obj': forms.Select(attrs={'class': 'input-field'}),
        }

    def __init__(self, *args, **kwargs):
        # Filtering the dropdown so only classes of the current institution appear
        institution = kwargs.pop('institution', None)
        super(StudentForm, self).__init__(*args, **kwargs)
        if institution:
            self.fields['class_obj'].queryset = Classes.objects.filter(institution=institution)
            self.fields['class_obj'].empty_label = "Choose a Class"

    def clean_password(self):
        
        password = self.cleaned_data.get('password')

        if len(password) < 6:
            raise forms.ValidationError("Password is too short (min 6).")
        if not re.search(r'[A-Z]', password):
            raise forms.ValidationError("Password must have an uppercase letter.")
        if not re.search(r'[0-9]', password):
            raise forms.ValidationError("Password must have at least one digit.")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise forms.ValidationError("Password must have a special character.")
        if not re.search(r'[a-z]', password):
            raise forms.ValidationError("Password must have at least one lowercase letter.")
            
        return password

class SubjectForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'input-field',
            'placeholder': '••••••••'
        }),
        max_length=191,
        help_text="Required: 6+ chars, 1 uppercase, 1 digit, 1 special char."
    )

    class Meta:
        model = Subjects
        fields = ['subject_name', 'subject_head', 'email', 'password', 'class_obj']
        
        widgets = {
            'subject_name': forms.TextInput(attrs={
                'placeholder': 'e.g. Mathematics, Physics',
                'class': 'input-field'
            }),
            'subject_head': forms.TextInput(attrs={
                'placeholder': 'e.g. Dr. Jane Doe',
                'class': 'input-field'
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'subject-admin@edu.com',
                'class': 'input-field'
            }),
            'class_obj': forms.Select(attrs={
                'class': 'input-field'
            }),
        }
        
    def __init__(self, *args, **kwargs):
        # Filtering the dropdown so only classes of the current institution appear
        institution = kwargs.pop('institution', None)
        super(SubjectForm, self).__init__(*args, **kwargs)
        if institution:
            self.fields['class_obj'].queryset = Classes.objects.filter(institution=institution)
            self.fields['class_obj'].empty_label = "Choose a Class"

        
    def clean_password(self):
        
        password = self.cleaned_data.get('password')

        if len(password) < 6:
            raise forms.ValidationError("Password is too short (min 6).")
        if not re.search(r'[A-Z]', password):
            raise forms.ValidationError("Password must have an uppercase letter.")
        if not re.search(r'[0-9]', password):
            raise forms.ValidationError("Password must have at least one digit.")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise forms.ValidationError("Password must have a special character.")
        if not re.search(r'[a-z]', password):
            raise forms.ValidationError("Password must have at least one lowercase letter.")
            
        return password