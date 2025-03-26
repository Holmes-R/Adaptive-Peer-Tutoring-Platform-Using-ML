from django.contrib.auth.models import User
from django.contrib.auth import login as auth_login
from django.db import IntegrityError
from django.http import JsonResponse
from django.urls import reverse
from translate import Translator
from .models import LoginForm, Home, StudentID, UploadFile, Feedback
from .forms import UploadForm
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
import json
from django.utils import timezone
import logging
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.decorators import throttle_classes
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
import torch
import sentencepiece
from gtts import gTTS
import os
import pyttsx3
from comtypes import CoInitialize, CoUninitialize
from django.conf import settings
from django.contrib.auth.decorators import login_required
from googletrans import Translator as GoogleTranslator
from django.contrib import messages
from django.contrib.auth import authenticate, login

# Home View

def home(request):
    return render(request, 'home.html')

# Login User
@csrf_exempt
def loginUser(request):
    if request.method == 'GET':
        return render(request, 'login.html')

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format."}, status=400)

        name = data.get('name')
        email = data.get('email')
        password = data.get('user_password')
        confirm_password = data.get('confirm_password')

        if not all([name, email, password, confirm_password]):
            return JsonResponse({"error": "All fields are required."}, status=400)

        if password != confirm_password:
            return JsonResponse({"error": "Passwords do not match."}, status=400)

        user, created = LoginForm.objects.get_or_create(email=email)
        if not created:
            return JsonResponse({"error": "User with this email already exists."}, status=400)

        user.name = name
        user.user_password = password
        user.confirm_password = confirm_password
        user.save()

        django_user = User.objects.filter(email=email).first()
        if not django_user:
            django_user = User.objects.create_user(username=email, email=email, password=password)
            django_user.save()

        auth_login(request, django_user)

        user.generate_otp()

        redirect_url = reverse('otp_verification') + f"?email={email}"
        return JsonResponse({"redirect_url": redirect_url}, status=200)
    return JsonResponse({"error": "Invalid request method."}, status=405)

@csrf_exempt
def otp_verification(request):
    email = request.GET.get('email')
    if not email:
        return JsonResponse({"error": "Email is required."}, status=400)

    return render(request, 'otp_verification.html', {'email': email})
@csrf_exempt
def verify_otp(request, email):
    print(f"Received {request.method} request for email: {email}")  # Debugging Log

    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method. Only POST is allowed."}, status=405)

    try:
        data = json.loads(request.body)
        print("Received Data:", data)  # Debugging Log
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format."}, status=400)

    otp_entered = data.get("otp")
    if not otp_entered:
        return JsonResponse({"error": "OTP is required."}, status=400)
    try:
        otp_instance = LoginForm.objects.get(email=email, generated_otp=otp_entered)
        print(f"✅ OTP Found: {otp_instance}")  # Debugging Log
    except OTP.DoesNotExist:
        return JsonResponse({"error": "Invalid OTP."}, status=400)

    if not otp_instance.is_otp_valid(otp_entered):
        return JsonResponse({"error": "OTP expired."}, status=400)

    print("✅ OTP Verified Successfully")
    return JsonResponse({
        "message": "OTP verified successfully!",
        "redirect_url": "/information/" + f"?email={email}" # Redirect to student information page
    }, status=200)

@csrf_exempt
def getInformation(request):
    print(f"Received {request.method} request")  # Debugging Log

    if request.method == "GET":
        email = request.GET.get('email')
        return render(request,'student_information.html',{"email":email},status=200)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            print("Received Data:", data)  # Debugging Log
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format."}, status=400)

        email = data.get('email')
        password = data.get('user_password')
        print(email)
        if not email:
            return JsonResponse({"error": "Email is required."}, status=400)

        login_form_instance = LoginForm.objects.filter(email=email).first()

        if not login_form_instance:
            return JsonResponse({"error": "Unauthorized. Please sign up or sign in first."}, status=401)

        college_name = data.get('college_name')
        course = data.get('course')
        year = data.get('year')
        CGPA = data.get('CGPA')
        student_choice = data.get('student_choice')
        cgpa_percentage = data.get('cgpa_percentage')
        cgpa_number = data.get('cgpa_number')

        if CGPA == 'percentage' and not cgpa_percentage:
            return JsonResponse({"error": "CGPA percentage is required when CGPA type is 'percentage'."}, status=400)
        elif CGPA == 'cgpa' and not cgpa_number:
            return JsonResponse({"error": "CGPA number is required when CGPA type is 'cgpa'."}, status=400)

        try:
            print(login_form_instance)
            home_instance, created = Home.objects.update_or_create(
                student_name=login_form_instance,
                defaults={
                    'college_name': college_name,
                    'course': course,
                    'year': year,
                    'CGPA': CGPA,
                    'student_choice': student_choice,
                    'cgpa_percentage': float(cgpa_percentage) if CGPA == 'percentage' else None,
                    'cgpa_number': float(cgpa_number) if CGPA == 'cgpa' else None,
                }
            )
            student_id_instance, _ = StudentID.objects.update_or_create(
    student=login_form_instance,
    defaults={'password': login_form_instance.user_password}  # Ensure correct field mapping
)

            return JsonResponse({
    "message": "Details saved or updated successfully!",
    "student_id": student_id_instance.unique_id  # Send unique_id to frontend
}, status=201)

        except IntegrityError as e:
            return JsonResponse({"error": f"Integrity Error: {str(e)}"}, status=500)


# Sign-In User
@csrf_exempt
def signInUser(request):
    if request.method == "GET":
        return render(request,'signup.html',status=200)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            unique_id = data.get('unique_id')
            password = data.get('password')
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format."}, status=400)

        if not unique_id or not password:
            return JsonResponse({"error": "Both Unique ID and Password are required."}, status=400)

        student_id = StudentID.objects.filter(unique_id=unique_id).first()

        if not student_id:
            return JsonResponse({"error": "Invalid Unique ID."}, status=400)

        if student_id.password == password:
            return JsonResponse({"message": "Login successful."}, status=200)
        else:
            return JsonResponse({"error": "Invalid password."}, status=400)

    return JsonResponse({"error": "Invalid request method."}, status=405)

# Translation and Text-to-Speech
model_name = "facebook/m2m100_418M"
tokenizer = M2M100Tokenizer.from_pretrained(model_name)
model = M2M100ForConditionalGeneration.from_pretrained(model_name)

LANGUAGES = [
    ("en", "English"),
    ("fr", "French"),
    ("es", "Spanish"),
    ("de", "German"),
    ("it", "Italian"),
    ("hi", "Hindi"),
    ("ur", "Urdu"),
    ("ta", "Tamil"),
    ("ml", "Malayalam"),
]

def translate_text(text, target_lang):
    if target_lang in ['ta', 'te', 'ml']: 
        return translate_with_other_method(text, target_lang)
    elif target_lang in ['hi', 'kn', 'mr', 'gu', 'bn', 'pa', 'ur']:  
        return translate_with_google(text, target_lang)
    else:
        return translate_with_m2m100(text, target_lang)

def translate_with_m2m100(text, target_lang):
    tokenizer.src_lang = "en"
    encoded_text = tokenizer(text, return_tensors="pt")
    generated_tokens = model.generate(
        **encoded_text,
        forced_bos_token_id=tokenizer.get_lang_id(target_lang)
    )
    translated_text = tokenizer.decode(generated_tokens[0], skip_special_tokens=True)
    return translated_text

def translate_with_other_method(text, target_lang):
    lang_mapping = {
        'ta': 'ta',  # Tamil
        'te': 'te',  # Telugu
        'ml': 'ml',  # Malayalam
    }
    translator = Translator(to_lang=lang_mapping.get(target_lang, "en"))
    return translator.translate(text)

def translate_with_google(text, target_lang):
    google_translator = GoogleTranslator()
    translated_text = google_translator.translate(text, dest=target_lang).text
    return translated_text

def upload_file(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Unauthorized. Please sign in first."}, status=401)

    email = request.user.email  # Get the logged-in user's email

    if request.method == 'POST':
        print(request.POST)  # Debugging - Check received data

        password = request.POST.get('password')

        # Fetch the user using email
        user = LoginForm.objects.filter(email=email).first()

        if not user:
            return JsonResponse({"error": "Unauthorized. Please check your email."}, status=401)

        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save(commit=False)  # Don't save yet
            upload.student_upload = user  # Assign the logged-in user
            upload.save()  # Now save the record

            if upload.summary:
                return redirect('summary_detail', pk=upload.pk)
            elif upload.keywords:
                return redirect('keywords_detail', pk=upload.pk)
            else:
                return redirect('file_list')

    else:
        form = UploadForm()

    return render(request, 'upload.html', {'form': form, 'email': email})


def speak(text, language="en"):
    try:
        audio_dir = os.path.join(settings.MEDIA_ROOT, 'audio')
        os.makedirs(audio_dir, exist_ok=True)
        
        audio_file = os.path.join(audio_dir, f"{hash(text)}_{language}.mp3")
        
        if not os.path.exists(audio_file):  
            try:
                tts = gTTS(text=text, lang=language)
                tts.save(audio_file)
                print(f"Audio file saved: {audio_file}")
            except Exception as e:
                print(f"gTTS Error: {e}, falling back to pyttsx3.")
                try:
                    engine = pyttsx3.init()
                    engine.save_to_file(text, audio_file)
                    engine.runAndWait()
                    print(f"Audio file saved with pyttsx3: {audio_file}")
                except Exception as e:
                    print(f"pyttsx3 Error: {e}")
        
        return audio_file 
    except Exception as e:
        print(f"Error in speech generation: {e}")
        return None

def summary_detail(request, pk):
    upload = get_object_or_404(UploadFile, pk=pk)
    print("Summary:", upload.summary)  # Debugging line

    translated_summary = None
    if request.method == 'POST':
        action = request.POST.get('action')
        target_lang = request.POST.get('target_lang')

        if action == 'translate' and upload.summary:
            translated_summary = translate_with_m2m100(upload.summary, target_lang)

        elif action == 'speak':
            text_to_speak = upload.summary if not translated_summary else translated_summary
            if text_to_speak:
                speak(text_to_speak, language=target_lang)

    return render(request, 'file_summary.html', {
        'upload': upload,
        'translated_summary': translated_summary,
        'languages': LANGUAGES,
    })


def keywords_detail(request, pk):
    upload = get_object_or_404(UploadFile, pk=pk)
    keywords = upload.keywords.split(',') if upload.keywords else []
    translated_keywords = None

    if request.method == 'POST':
        action = request.POST.get('action')
        target_lang = request.POST.get('target_lang')

        if action == 'translate' and upload.keywords:
            translated_keywords = [translate_with_m2m100(kw, target_lang) for kw in keywords]

        elif action == 'speak':
            text_to_speak = ", ".join(keywords) if not translated_keywords else ", ".join(translated_keywords)
            if text_to_speak:
                speak(text_to_speak, language=target_lang)

    return render(request, 'file_keywords.html', {
        'upload': upload,
        'keywords': keywords,
        'translated_keywords': translated_keywords,
        'languages': LANGUAGES,
    })

def file_list(request):
    files = UploadFile.objects.all()
    return render(request, 'file_list.html', {'files': files})

# Feedback Submission
def submit_feedback_summary(request):
    if request.method == "POST":
        feedback_text = request.POST.get('feedback')
        user = request.user  
        feedback = Feedback(text=feedback_text, category="summary", user=user)
        feedback.save()
        return redirect('thank_you')  
    return render(request, 'files_summary.html')

def submit_feedback_keywords(request):
    if request.method == "POST":
        feedback_text = request.POST.get('feedback')
        user = request.user 
        feedback = Feedback(text=feedback_text, category="keywords", user=user)
        feedback.save() 
        return redirect('thank_you') 
    return render(request, 'files_keyword.html')

# Admin Login
def admin_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)
            return redirect('/admin')  
        else:
            messages.error(request, "Invalid email or password. Please try again.")

    return render(request, 'admin.html')