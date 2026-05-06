# استخدم نسخة Python الرسمية
FROM python:3.10-slim

# تعيين مجلد العمل
WORKDIR /app

# تثبيت الأدوات اللازمة
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# نسخ ملف المتطلبات أولاً لتسريع البناء
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع
COPY . .

# فتح المنافذ المطلوبة
EXPOSE 8501
EXPOSE 8000

# تشغيل ملف التشغيل الأساسي (الذي يدمج الداتا ويشغل السيرفرين)
CMD ["python", "streamlit_app.py"]
