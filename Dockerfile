# เลือก base image ของ Python
FROM python:3.9-slim

# ติดตั้ง dependencies ที่จำเป็นสำหรับการใช้งาน PyNaCl
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# กำหนด working directory ใน container
WORKDIR /app

# คัดลอกไฟล์ requirements.txt เข้า container
COPY requirements.txt /app/

# ติดตั้ง dependencies จาก requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# คัดลอกโค้ดทั้งหมดเข้า container
COPY . /app

# คำสั่งรันไฟล์ python เมื่อ container เริ่มต้น
CMD ["python", "main.py"]