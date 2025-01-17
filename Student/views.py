from django.contrib.auth.models import User
from django.contrib.auth import login as auth_login
from django.db import IntegrityError
from django.http import JsonResponse
from .models import LoginForm ,Home ,StudentID ,UploadFile
from .forms import UploadForm
from django.shortcuts import get_object_or_404 , redirect , render
from django.views.decorators.csrf import csrf_exempt
import json
from django.utils import timezone
import logging
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.decorators import  throttle_classes
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
import torch
import sentencepiece
from gtts import gTTS
import os
import pyttsx3
from comtypes import CoInitialize, CoUninitialize
from django.conf import settings
from .models import Feedback, LoginForm
from django.contrib.auth.decorators import login_required



@csrf_exempt
@throttle_classes([AnonRateThrottle, UserRateThrottle])
def loginUser(request):
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
        if django_user:
            auth_login(request, django_user)
        else:
            django_user = User.objects.create_user(username=email, email=email, password=password)
            django_user.save()
            auth_login(request, django_user)

        user.generate_otp()

        return JsonResponse({"message": "User created and logged in successfully. OTP sent to email."}, status=200)

    return JsonResponse({"error": "Invalid request method."}, status=405)


logger = logging.getLogger(__name__)
@csrf_exempt
def verify_otp(request, email):
    if request.method == 'POST':
        try:

            data = json.loads(request.body)
            user_otp = data.get('user_otp')
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format."}, status=400)

        if not user_otp:
            logger.error("OTP not provided in the request.")
            return JsonResponse({"error": "OTP is required."}, status=400)

        logger.debug(f"User OTP received: {user_otp}")
        
        user = get_object_or_404(LoginForm, email=email)

        logger.debug(f"Generated OTP: {user.generated_otp}")
        
        if user.generated_otp == str(user_otp):
            if user.otp_expiry and timezone.now() <= user.otp_expiry:
                user.user_otp = user_otp  
                user.save()
                return JsonResponse({"message": "OTP verified successfully."}, status=200)
            else:
                logger.debug("OTP expired.")
                return JsonResponse({"error": "OTP has expired."}, status=400)
        else:
            logger.debug("OTP does not match.")
            return JsonResponse({"error": "Invalid OTP."}, status=400)

    return JsonResponse({"error": "Invalid request method."}, status=405)

@csrf_exempt
def getInformation(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format."}, status=400)

        password = data.get('user_password')

        if not password:
            return JsonResponse({"error": "Password is required."}, status=400)

        college_name = data.get('college_name')
        course = data.get('course')
        year = data.get('year')
        CGPA = data.get('CGPA')
        student_choice = data.get('student_choice')
        cgpa_percentage = data.get('cgpa_percentage')
        cgpa_number = data.get('cgpa_number')
        email = data.get('email') 

        if not email:
            return JsonResponse({"error": "Email is required to identify the student."}, status=400)

        if CGPA == 'percentage' and not cgpa_percentage:
            return JsonResponse({"error": "CGPA percentage is required when CGPA type is 'percentage'."}, status=400)
        elif CGPA == 'cgpa' and not cgpa_number:
            return JsonResponse({"error": "CGPA number is required when CGPA type is 'cgpa'."}, status=400)

        try:
            login_form_instance = LoginForm.objects.filter(email=email).first()

            if login_form_instance:
                login_form_instance.user_password = password
                login_form_instance.save()
            else:
                login_form_instance = LoginForm.objects.create(email=email, user_password=password)

            home_instance, created = Home.objects.update_or_create(
                student_name=login_form_instance, 
                defaults={
                    'college_name': college_name,
                    'course': course,
                    'year': year,
                    'CGPA': CGPA,
                    'student_choice': student_choice,
                    'cgpa_percentage': cgpa_percentage if CGPA == 'percentage' else None,
                    'cgpa_number': cgpa_number if CGPA == 'cgpa' else None,
                }
            )

            if created:
                home_instance.save()

            student_id_instance, created = StudentID.objects.update_or_create(
                student=login_form_instance, 
                defaults={'password': password}
            )

            return JsonResponse({
                "message": "Details saved or updated successfully!",
                "student_id": student_id_instance.unique_id  
            }, status=201)

        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)
        except IntegrityError as e:
            return JsonResponse({"error": f"Integrity Error: {str(e)}"}, status=500)

    return JsonResponse({"error": "Invalid request method."}, status=405)


@csrf_exempt
def signInUser(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            unique_id = data.get('unique_id') 
            password = data.get('password')

            if not unique_id or not password:
                return JsonResponse({"error": "Unique ID and password are required."}, status=400)

            try:
                student_id_instance = StudentID.objects.get(unique_id=unique_id) 
                if student_id_instance.password == password:  
                    return JsonResponse({"message": "Sign in successful!"}, status=200)
                else:
                    return JsonResponse({"error": "Invalid password."}, status=401)
            except StudentID.DoesNotExist:
                return JsonResponse({"error": "Unique ID does not exist."}, status=404)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format."}, status=400)

    return JsonResponse({"error": "Invalid request method."}, status=405)

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
    ("ml", "Malayalam"),
    ("te", "Telugu"),
    ("ur", "Urdu"),
    ("ta", "Tamil")
]

def upload_file(request):
    if request.method == 'POST':
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save()

            if upload.summary:  
                return redirect('summary_detail', pk=upload.pk)
            elif upload.keywords: 
                return redirect('keywords_detail', pk=upload.pk)
            else:
                return redirect('file_list')  
    else:
        form = UploadForm()

    return render(request, 'upload.html', {'form': form})

def translate_with_m2m100(text, target_lang):
    """
    Translate text using M2M-100 model.
    """
    tokenizer.src_lang = "en" 
    encoded_text = tokenizer(text, return_tensors="pt")
    generated_tokens = model.generate(**encoded_text, forced_bos_token_id=tokenizer.get_lang_id(target_lang))
    translated_text = tokenizer.decode(generated_tokens[0], skip_special_tokens=True)
    return translated_text
def speak(text, language="en"):
    try:
        # Ensure the audio directory exists
        audio_dir = os.path.join(settings.MEDIA_ROOT, 'audio')
        os.makedirs(audio_dir, exist_ok=True)
        
        # Generate a unique filename
        audio_file = os.path.join(audio_dir, f"{hash(text)}_{language}.mp3")
        
        if not os.path.exists(audio_file):  # Avoid regenerating the same file
            try:
                # Use gTTS for speech generation
                tts = gTTS(text=text, lang=language)
                tts.save(audio_file)
                print(f"Audio file saved: {audio_file}")
            except Exception as e:
                print(f"gTTS Error: {e}, falling back to pyttsx3.")
                try:
                    # Use pyttsx3 as a fallback
                    engine = pyttsx3.init()
                    engine.save_to_file(text, audio_file)
                    engine.runAndWait()
                    print(f"Audio file saved with pyttsx3: {audio_file}")
                except Exception as e:
                    print(f"pyttsx3 Error: {e}")
        
        return audio_file  # Return the file path for playback
    except Exception as e:
        print(f"Error in speech generation: {e}")
        return None

def summary_detail(request, pk):
    upload = get_object_or_404(UploadFile, pk=pk)
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

@login_required
def submit_feedback_summary(request):
    if request.method == "POST":
        feedback_text = request.POST.get('feedback')
        user = request.user  # Assuming the user is logged in

        # Save feedback for summary category
        feedback = Feedback(text=feedback_text, category="summary", user=user)
        feedback.save()

        return redirect('thank_you')  # Redirect to a thank you page or confirmation

    return render(request, 'files_summary.html')

@login_required
def submit_feedback_keywords(request):
    if request.method == "POST":
        feedback_text = request.POST.get('feedback')
        user = request.user  # Assuming the user is logged in

        # Save feedback for keywords category
        feedback = Feedback(text=feedback_text, category="keywords", user=user)
        feedback.save()

        return redirect('thank_you')  # Redirect to a thank you page or confirmation

    return render(request, 'files_keyword.html')