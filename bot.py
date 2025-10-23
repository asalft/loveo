# bot.py
import os
import asyncio
import logging
import random
from telethon import TelegramClient
from telethon.errors import RPCError
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.types import InputPhoto
from telethon.sessions import StringSession  # لا يستخدم ملفات SQLite

# إعداد اللوقينج
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
log = logging.getLogger(__name__)

# متغيرات بيئة
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION", "")
IMAGES_DIR = os.environ.get("IMAGES_DIR", "images")
INTERVAL = int(os.environ.get("INTERVAL", "300"))  # بالثواني
DELETE_OLD = os.environ.get("DELETE_OLD", "yes").lower() in ("yes", "true", "1")

if API_ID == 0 or not API_HASH or not SESSION_STRING:
    log.error("API_ID و API_HASH و SESSION مطلوبة كمتغيرات بيئة. أوقف التشغيل.")
    raise SystemExit(1)

# إنشاء العميل باستخدام StringSession
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

async def get_image_paths(dirpath):
    if not os.path.isdir(dirpath):
        log.error("مجلد الصور غير موجود: %s", dirpath)
        return []
    files = [os.path.join(dirpath, f) for f in os.listdir(dirpath)
             if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
    if not files:
        log.error("لا توجد صور صالحة في المجلد '%s'.", dirpath)
    else:
        log.info("تم العثور على هذه الصور: %s", files)
    return files

async def upload_and_set(photo_path):
    try:
        log.info("رفع الصورة: %s", photo_path)
        file = await client.upload_file(photo_path)
        await client(UploadProfilePhotoRequest(file))
        log.info("تم تعيين الصورة بنجاح.")
    except RPCError as e:
        log.exception("خطأ أثناء رفع / تعيين الصورة: %s", e)
    except Exception as e:
        log.exception("خطأ غير متوقع: %s", e)

async def delete_old_profile_photos(keep=1):
    try:
        photos = await client.get_profile_photos('me')
        if len(photos) <= keep:
            return
        to_delete = photos[:-keep]
        if not to_delete:
            return
        inputs = [InputPhoto(id=p.id, access_hash=getattr(p, 'access_hash', 0), file_reference=p.file_reference) 
                  for p in to_delete if getattr(p, 'id', None) is not None]
        if inputs:
            await client(DeletePhotosRequest(inputs))
            log.info("حُذِف %d من صور الملف الشخصي القديمة.", len(inputs))
    except Exception as e:
        log.exception("فشل حذف الصور القديمة: %s", e)

async def main_loop():
    images = await get_image_paths(IMAGES_DIR)
    if not images:
        log.error("لا توجد صور صالحة. أوقف التشغيل.")
        return

    while True:
        try:
            image = random.choice(images)  # اختيار صورة عشوائية
            await upload_and_set(image)
            if DELETE_OLD:
                await delete_old_profile_photos(keep=1)
        except Exception as e:
            log.exception("خطأ في الحلقة الرئيسية: %s", e)

        log.info("ينتظر %s ثانية قبل تغيير الصورة التالية...", INTERVAL)
        await asyncio.sleep(INTERVAL)

async def run():
    await client.start()
    log.info("تم تشغيل Telethon و تسجيل الدخول.")
    try:
        await main_loop()
    finally:
        await client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        log.info("تم الإيقاف بواسطة المستخدم.")
