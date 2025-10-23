# bot.py
import os
import asyncio
import logging
from telethon import TelegramClient
from telethon.errors import RPCError
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.types import InputPhoto

# إعداد اللوقينج
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
log = logging.getLogger(__name__)

# متغيرات من البيئة (set these in Heroku Config Vars)
API_ID = int(os.environ.get("API_ID", "0"))        # required
API_HASH = os.environ.get("API_HASH", "")         # required
SESSION = os.environ.get("SESSION", "session")    # يمكن أن يكون string session أو اسم ملف جلسة
IMAGES_DIR = os.environ.get("IMAGES_DIR", "images")  # مجلد الصور داخل الريبو
INTERVAL = int(os.environ.get("INTERVAL", "300"))    # بالثواني (افتراضي 300 = 5 دقائق)
DELETE_OLD = os.environ.get("DELETE_OLD", "yes").lower() in ("yes", "true", "1")

if API_ID == 0 or not API_HASH:
    log.error("API_ID و API_HASH مطلوبان كمتغير بيئة. أوقف التشغيل.")
    raise SystemExit(1)

client = TelegramClient(SESSION, API_ID, API_HASH)

async def get_image_paths(dirpath):
    if not os.path.isdir(dirpath):
        log.error("مجلد الصور غير موجود: %s", dirpath)
        return []
    files = []
    for fname in sorted(os.listdir(dirpath)):
        if fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            files.append(os.path.join(dirpath, fname))
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
    # يحذف صور البروفايل القديمة مع الإبقاء على أحدث `keep`
    try:
        photos = await client.get_profile_photos('me')
        if len(photos) <= keep:
            return
        # نحتفظ بالأحدث (photos كائنات مرتبة من الأقدم إلى الأحدث؟ نتحقق بالترتيب)
        to_delete = photos[:-keep]
        if not to_delete:
            return
        # تحويل إلى InputPhoto
        inputs = []
        for p in to_delete:
            # كل p هو Photo; نحتاج الى InputPhoto مع id و access_hash
            if getattr(p, 'id', None) is not None:
                inputs.append(InputPhoto(id=p.id, access_hash=getattr(p, 'access_hash', 0), file_reference=p.file_reference))
        if inputs:
            await client(DeletePhotosRequest(inputs))
            log.info("حُذِف %d من صور الملف الشخصي القديمة.", len(inputs))
    except Exception as e:
        log.exception("فشل حذف الصور القديمة: %s", e)

async def main_loop():
    images = await get_image_paths(IMAGES_DIR)
    if not images:
        log.error("لا توجد صور في المجلد '%s'. أضف صور ثم أعد التشغيل.", IMAGES_DIR)
        return

    idx = 0
    # دورة لانهائية: كل INTERVAL ثانية نغير الصورة
    while True:
        try:
            image = images[idx % len(images)]
            await upload_and_set(image)
            if DELETE_OLD:
                # احتفظ بأحدث صورة واحدة فقط
                await delete_old_profile_photos(keep=1)
        except Exception as e:
            log.exception("خطأ في الحلقة الرئيسية: %s", e)

        idx += 1
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
