# Smart Traffic Data Pipeline

## نظام ذكي لمراقبة وتحليل حركة المرور في المدن

### Apache NiFi | PostgreSQL | Hadoop HDFS | Docker | Python

---

## جدول المحتويات

1. [السيناريو الواقعي](#1-السيناريو-الواقعي)
2. [مشكلة البيانات](#2-مشكلة-البيانات)
3. [مصادر البيانات - الحقول الكاملة](#3-مصادر-البيانات---الحقول-الكاملة)
4. [هندسة النظام](#4-هندسة-النظام)
5. [خط أنابيب NiFi](#5-خط-أنابيب-nifi)
6. [استراتيجيات التنظيف](#6-استراتيجيات-التنظيف)
7. [أفضل الممارسات](#7-أفضل-الممارسات)
8. [التحديات والحلول](#8-التحديات-والحلول)
9. [دليل التشغيل](#9-دليل-التشغيل)
10. [مؤشرات الأداء والمراقبة](#10-مؤشرات-الأداء-والمراقبة)
11. [خطة التوسع المستقبلية](#11-خطة-التوسع-المستقبلية)
12. [الملاحق](#12-الملاحق)

---

## 1. السيناريو الواقعي

### مدينة ذكية تراقب حركة المرور

في مدينة كبرى مثل الرياض أو دبي، تنتشر آلاف الحساسات والكاميرات في التقاطعات الرئيسية. هذه الحساسات ترسل بيانات **كل ثانية** عن حالة الطرق. الهدف ليس فقط مراقبة الحركة، بل **التنبؤ بالازدحام قبل حدوثه**، واكتشاف الحوادث تلقائيًا، وتعديل توقيت الإشارات الضوئية ديناميكيًا.

في نفس الوقت، هناك **نظام مركزي** (قاعدة بيانات) يحتفظ بسجل لجميع التقاطعات: أسماؤها، أحياؤها، نوع الإشارات فيها، تواريخ آخر صيانة، وغيرها. هذا السجل يتغير ببطء: تقاطع جديد يُضاف عند توسع المدينة، إشارة تُصان، توقيت يتغير، برنامج ثابت يُحدث.

**التحدي الهندسي:** كيف نجمع هذين المصدرين معًا - أحدهما سريع ومتدفق (آلاف القراءات في الثانية)، والآخر بطيء التغير (تحديثات يومية أو أسبوعية) - ننظفهما، ندمجهما، ونخزنهما لتحليلهما لاحقًا؟

**الجهات المستفيدة من هذا النظام:**
- **غرفة التحكم المروري:** مراقبة لحظية للازدحام والحوادث
- **قسم التخطيط العمراني:** تحليل أنماط الحركة لتخطيط طرق جديدة
- **قسم الصيانة:** معرفة الإشارات التي تحتاج صيانة بناءً على أدائها
- **الدفاع المدني:** اكتشاف الحوادث وتوجيه فرق الطوارئ

---

## 2. مشكلة البيانات

### لماذا البيانات "متسخة"؟

في الأنظمة الحقيقية، البيانات ليست مثالية أبدًا. صممنا مولدات البيانات لتنتج **عيوبًا متعمدة** تحاكي الواقع. الهدف: بناء خط أنابيب قوي يستطيع التعامل مع فوضى البيانات الحقيقية.

### تصنيف العيوب

صنفنا العيوب إلى **5 فئات** رئيسية:

| الفئة | الوصف | خطورتها |
|-------|-------|---------|
| **Missing Values** | قيم فارغة أو null | متوسطة |
| **Invalid Formats** | نص مكان رقم، تاريخ خاطئ | عالية |
| **Logical Errors** | قيم سالبة، تناقضات | عالية |
| **Duplicates** | سجلات مكررة | منخفضة |
| **Outliers** | قيم متطرفة غير منطقية | متوسطة |

---

## 3. مصادر البيانات - الحقول الكاملة

### المصدر الأول: محاكي حركة المرور (Traffic Sensor Simulator)

**ملف:** `generate_transactions.py`
**الصيغة:** NDJSON (Newline Delimited JSON)
**معدل التوليد:** ملف جديد كل 2-5 ثوانٍ
**محتوى الملف:** 3-8 سجلات
**التسمية:** `Transaction_YYYYMMDD_HHMMSS_microseconds.json`

#### الحقول الكاملة للمصدر الأول:

| # | اسم الحقل | النوع | الوصف | مصدر القيمة | العيوب المتعمدة |
|---|-----------|-------|-------|-------------|-----------------|
| 1 | `event_id` | UUID | معرف فريد للحدث المروري | `uuid.uuid4()` | 12% تكرار (DUPLICATE_EVENT) |
| 2 | `intersection_id` | VARCHAR(8) | معرف التقاطع (INT-0001 إلى INT-0030) | قائمة عشوائية | طبيعي |
| 3 | `vehicle_type` | ENUM | نوع المركبة | car, truck, bus, motorcycle, emergency | car أكثر شيوعًا (محاكاة للواقع) |
| 4 | `vehicle_count` | INTEGER | عدد المركبات في آخر 5 ثوانٍ | 0-30 عادي | null, -1, "unknown" |
| 5 | `avg_speed_kmh` | FLOAT | متوسط السرعة (كم/س) | 0-80 عادي | null, -10.0, 150.0 |
| 6 | `congestion_level` | ENUM | مستوى الازدحام | smooth, moderate, heavy, gridlock | null, ""، قيمة متناقضة 20% |
| 7 | `district` | VARCHAR(50) | الحي | Downtown, Industrial Zone, إلخ | null, ""، "downtown" (حالة خاطئة) |
| 8 | `lane_id` | INTEGER | رقم المسار | 1-4 | null |
| 9 | `temperature_c` | FLOAT | درجة حرارة الأسفلت (مئوية) | 20-70 عادي | null, -99.9 (كود خطأ), 95.0 |
| 10 | `visibility_m` | FLOAT | مدى الرؤية (متر) | 50-5000 عادي | null, 0.0, -1.0 |
| 11 | `accident_flag` | BOOLEAN | هل يوجد حادث؟ | منطق: سرعة < 5 + ازدحام = true | null، true مع سرعة عالية (خطأ) |
| 12 | `signal_status` | ENUM | حالة الإشارة الضوئية | green, yellow, red, flashing | null |
| 13 | `event_timestamp` | TIMESTAMP | الطابع الزمني للحدث | ISO 8601 | صحيح دائمًا |

#### منطق توليد العيوب (مثال):

```python
# مثال: توليد vehicle_count مع عيوب
def generate_vehicle_count():
    return random.choice([
        random.randint(0, 30),    # 80% - قيمة صحيحة
        None,                      # 10% - حساس معطل
        -1,                        # 5% - كود خطأ
        "unknown"                  # 5% - خطأ تنسيق
    ])
```

---

### المصدر الثاني: قاعدة بيانات التقاطعات (Intersection Reference Database)

**ملف:** `generate_db.py`
**القاعدة:** PostgreSQL 13
**الجدول:** `intersections`
**معدل التحديث:** كل 10-15 ثانية (30% إضافة، 70% تعديل)

#### مخطط الجدول الكامل:

| # | اسم العمود | النوع | القيود | الوصف | العيوب المتعمدة |
|---|-----------|-------|--------|-------|-----------------|
| 1 | `intersection_id` | VARCHAR(10) | PRIMARY KEY | معرف التقاطع (INT-XXXX) | لا عيوب (مفتاح رئيسي) |
| 2 | `intersection_name` | VARCHAR(100) | NOT NULL | اسم الشارعين المتقاطعين | لا عيوب |
| 3 | `district` | VARCHAR(50) | - | الحي | null, "", "unknown" |
| 4 | `total_lanes` | INTEGER | - | عدد المسارات (2-4) | null |
| 5 | `has_camera` | BOOLEAN | - | هل فيه كاميرا مراقبة؟ | لا عيوب |
| 6 | `has_sensor` | BOOLEAN | - | هل فيه حساس أرضي؟ | لا عيوب |
| 7 | `signal_type` | VARCHAR(20) | - | نوع الإشارة | smart, fixed, adaptive, manual |
| 8 | `signal_timing_sec` | INTEGER | - | مدة الإشارة الخضراء (ثانية) | null, 0, -1, "N/A" |
| 9 | `last_maintenance` | DATE | - | تاريخ آخر صيانة | لا عيوب (لكن قد يكون قديمًا) |
| 10 | `status` | VARCHAR(20) | - | حالة التقاطع | active, maintenance, offline, null |
| 11 | `firmware_version` | VARCHAR(10) | - | نسخة برنامج الإشارة | null |
| 12 | `updated_at` | TIMESTAMP | DEFAULT NOW() | آخر تحديث (يُستخدم للاستخراج التزايدي) | لا عيوب |

#### منطق المحاكاة:

```python
# 30%: إضافة تقاطع جديد (توسع المدينة)
if random.random() < 0.30:
    add_new_intersection()

# 70%: تحديث تقاطع موجود (صيانة، تغيير توقيت، تحديث برنامج)
else:
    update_existing_intersection()
```

---

## 4. هندسة النظام

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DOCKER ENVIRONMENT                            │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ python-     │  │ python-     │  │          │  │              │  │
│  │ simulator   │  │ simulator   │  │ postgres │  │   hadoop     │  │
│  │ (Traffic)   │  │ (DB Gen)    │  │  :5432   │  │ :9870 :9000  │  │
│  └──────┬──────┘  └──────┬──────┘  └────┬─────┘  └──────┬───────┘  │
│         │                │              │               │          │
│         ▼                ▼              ▼               ▼          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      APACHE NIFI                             │   │
│  │                     :8443 (Web UI)                           │   │
│  │                                                              │   │
│  │  ListFile → FetchFile → SplitRecord → EvaluateJsonPath      │   │
│  │                                           (Traffic Fields)   │   │
│  │                                                              │   │
│  │  QueryDatabaseTable ───────────────→ EvaluateJsonPath        │   │
│  │  (Incremental)                        (DB Fields)            │   │
│  │                                           │                  │   │
│  │                              Funnel (Merge)                  │   │
│  │                                    │                         │   │
│  │                           QueryRecord (Dedup)                │   │
│  │                                    │                         │   │
│  │                           UpdateRecord (Clean)               │   │
│  │                                    │                         │   │
│  │                           PutFile → ExecuteStreamCommand     │   │
│  │                                         │                    │   │
│  └─────────────────────────────────────────┼────────────────────┘   │
│                                             │                       │
│                                    ┌────────▼───────┐               │
│                                    │   HDFS Storage  │               │
│                                    │  /traffic-data  │               │
│                                    └────────────────┘               │
└─────────────────────────────────────────────────────────────────────┘
```

### مكونات Docker

| الحاوية | الصورة | المنافذ | الوظيفة |
|---------|--------|---------|---------|
| nifi | apache/nifi:latest | 8443 | محرك تدفق البيانات |
| postgres | postgres:13 | 5432 | قاعدة البيانات التشغيلية |
| python-simulator | python-simulator:custom | - | مولدات البيانات |
| hadoop | itversity/itvdelab:latest | 9870, 9000 | نظام الملفات الموزع |

### المجلدات المشتركة

| المجلد | المستخدم من | الغرض |
|--------|-------------|-------|
| `./data/incoming` | python-simulator (كتابة)، nifi (قراءة) | ملفات JSON الواردة |
| `./data/scripts` | python-simulator | السكريبتات |
| `./hdfs-staging` | nifi (كتابة)، hadoop (قراءة) | منطقة انتقالية لـ HDFS |
| `./nifi-extensions` | nifi | مكتبات JDBC وإعدادات Hadoop |

---

## 5. خط أنابيب NiFi

### نظرة عامة على التدفق

```
[مصادر] → [استيعاب] → [تقسيم] → [استخراج] → [دمج] → [تنظيف] → [تخزين]
```

### المرحلة الأولى: استيعاب الملفات (File Ingestion)

| # | المعالج | النوع | الوظيفة | إعدادات رئيسية |
|---|---------|-------|---------|---------------|
| 1 | **Sensors-Incoming-Data** | ListFile | مراقبة مجلد `/data/incoming` | File Filter: `[^\.].*\.json`<br/>Min File Age: 5 sec<br/>Max Dir Listing Time: 10 sec |
| 2 | **Fetch-Sensor-Files** | FetchFile | قراءة محتوى الملفات | Completion Strategy: Move File<br/>Move Destination: `/data/processed` |

**لماذا ListFile + FetchFile وليس GetFile؟**
- **فصل المسؤوليات:** المراقبة منفصلة عن الجلب
- **إدارة أفضل للأخطاء:** فشل الجلب لا يؤثر على المراقبة
- **مرونة:** يمكن إضافة معالجات بينهما (فلترة، تحديد أولويات)
- **أداء:** ListFile خفيف، FetchFile يعمل فقط عند الحاجة

**الإعدادات الحرجة:**
- `Minimum File Age: 5 sec` — يمنع قراءة ملفات غير مكتملة
- `Completion Strategy: Move File` — يمنع إعادة قراءة نفس الملف

---

### المرحلة الثانية: التقسيم والاستخراج (Split & Extract)

| # | المعالج | النوع | الوظيفة |
|---|---------|-------|---------|
| 3 | **Split-JSON-Records** | SplitRecord | تقسيم كل ملف NDJSON إلى سجلات فردية |
| 4 | **Extract-JSON-Fields** | EvaluateJsonPath | استخراج 13 حقل مرور كـ FlowFile Attributes |

**Records Per Split: 1** — كل سجل JSON يصبح FlowFile مستقل.

---

### المرحلة الثالثة: استخراج قاعدة البيانات (Database Extraction)

| # | المعالج | النوع | الوظيفة |
|---|---------|-------|---------|
| 5 | **Fetch-Intersections-From-DB** | QueryDatabaseTable | استخراج تزايدي من PostgreSQL |
| 6 | **Extract-DB-Fields** | EvaluateJsonPath | استخراج 12 حقل تقاطع كـ FlowFile Attributes |

**الاستخراج التزايدي (Incremental Extraction):**
- `Maximum-value Columns: updated_at` — يسحب فقط السجلات المحدثة منذ آخر استخراج
- `Run Schedule: 10 sec` — يفحص التغييرات كل 10 ثوانٍ

---

### المرحلة الرابعة: الدمج والتنظيف (Merge & Clean)

| # | المعالج | النوع | الوظيفة | إعدادات |
|---|---------|-------|---------|---------|
| 7 | **Traffic-Data-Merge** | Funnel | دمج مساري البيانات (المرور + التقاطعات) | - |
| 8 | **Remove-Duplicates** | QueryRecord | إزالة السجلات المكررة | `SELECT DISTINCT * FROM FLOWFILE` |
| 9 | **Clean-Traffic-Data** | UpdateRecord | تنظيف القيم الشاذة والمفقودة | 7 قواعد تنظيف |

---

### المرحلة الخامسة: التخزين (Storage)

| # | المعالج | النوع | الوظيفة |
|---|---------|-------|---------|
| 10 | **Store-to-HDFS-Staging** | PutFile | حفظ الملفات في `/hdfs-staging` |
| 11 | **Move-to-HDFS** | ExecuteStreamCommand | نقل تلقائي إلى HDFS عبر WebHDFS |

---

## 6. استراتيجيات التنظيف

### مبرر الدمج قبل التنظيف

| المقارنة | تنظيف كل مصدر على حدة | دمج ثم تنظيف (المعتمد) |
|----------|----------------------|------------------------|
| عدد قواعد التنظيف | مكررة (×2) | مرة واحدة |
| اكتشاف التناقضات | صعب | سهل |
| الصيانة | أصعب | أسهل |
| قابلية التوسع | إضافة مصدر = إضافة قواعد جديدة | القواعد تبقى كما هي |

### قواعد التنظيف بالتفصيل

| # | الحقل | الشرط | القيمة البديلة | المنطق |
|---|-------|-------|---------------|--------|
| 1 | `vehicle_count` | null, سالب, نصي | `0` | إزالة غير الرقمي، تعويض السالب والفارغ |
| 2 | `avg_speed_kmh` | سالب | `0.0` | سرعة سالبة = خطأ حساس |
| 3 | `temperature_c` | > 75 أو < -50 | `25.0` | درجة حرارة معتدلة كقيمة افتراضية |
| 4 | `visibility_m` | ≤ 0 | `1000.0` | رؤية صفرية مستحيلة |
| 5 | `congestion_level` | فارغ أو null | `"unknown"` | تصنيف غير معروف |
| 6 | `signal_status` | فارغ أو null | `"unknown"` | حالة غير معروفة |
| 7 | `district` | فارغ أو null | `"Unassigned"` | حي غير محدد |

---

## 7. أفضل الممارسات

### Back Pressure (الضغط الخلفي)

| الموقع | Object Threshold | Size Threshold |
|--------|-----------------|----------------|
| الأنبوب بين FetchFile و SplitRecord | 10 | 10 MB |

**السلوك:** عند وصول عدد FlowFiles في قائمة الانتظار إلى 10، يتوقف FetchFile تلقائيًا حتى يفرغ SplitRecord بعض الملفات.

### Yield Duration (مدة التوقف)

| الموقع | القيمة | السبب |
|--------|--------|-------|
| Fetch-Intersections-From-DB | 10 sec | إعطاء PostgreSQL وقتًا للتعافي إذا تعطلت |

### Penalty Duration (مدة المعاقبة)

| الموقع | القيمة | السبب |
|--------|--------|-------|
| Remove-Duplicates | 10 sec | تأخير السجلات الفاشلة قبل إعادة محاولتها |

### Prioritizer (تحديد الأولويات)

| الموقع | النوع | السبب |
|--------|-------|-------|
| الأنبوب بين ListFile و FetchFile | FirstInFirstOut | ضمان معالجة الملفات بترتيب زمني |

---

## 8. التحديات والحلول

| # | التحدي | المظهر | التحليل | الحل |
|---|--------|--------|---------|------|
| 1 | SplitJSON لا يعمل | Out = 0 مع وجود مدخلات | SplitJSON يحتاج JSON Array، بياناتنا NDJSON | SplitRecord مع JsonTreeReader |
| 2 | PutHDFS غير موجود | المعالج غير مدرج | أُزيل إلى ملحق NAR خارجي | تحميل NAR + PutFile/WebHDFS كحل هجين |
| 3 | psycopg2 يختفي | ModuleNotFoundError بعد إعادة التشغيل | الحاوية لا تحتفظ بالمكتبات | Dockerfile مخصص (python-simulator:custom) |
| 4 | تقييم JSON لمصدرين | حقول مختلطة | المصدران لهما حقول مختلفة تمامًا | EvaluateJsonPath منفصل لكل مصدر |
| 5 | DetectDuplicate معقد | يحتاج DistributedMapCacheServer | غير موجود في NiFi 2.9.0 | QueryRecord مع SELECT DISTINCT |
| 6 | ConvertRecord لا يحول | بقيت البيانات JSON | قد يكون توافق إصدارات | قبول JSON كصيغة نهائية |
| 7 | FetchFile بطيء | يستغرق 10 دقائق للإخراج | إعدادات الجدولة والتوقيت | تقليل Max Dir Listing Time إلى 10s |
| 8 | ملفات JDBC تختفي | PostgreSQL-Pool يفشل | إعادة التشغيل تمسح الملفات المؤقتة | Docker Volume دائم (`nifi-extensions`) |

---

## 9. دليل التشغيل

### المتطلبات
- Docker و Docker Compose
- WSL2 أو Linux
- 8GB RAM على الأقل موصى بها

### بدء التشغيل

```bash
# 1. الدخول إلى مجلد المشروع
cd ~/nifi-project

# 2. بدء جميع الخدمات
docker compose up -d --build

# 3. انتظر حتى تبدأ جميع الخدمات (حوالي دقيقتين)
docker ps
# يجب أن ترى 4 حاويات: nifi, postgres, python-simulator, hadoop

# 4. شغّل مولدات البيانات (في طرفيتين منفصلتين)
docker exec -it python-simulator python3 /scripts/generate_transactions.py
docker exec -it python-simulator python3 /scripts/generate_db.py

# 5. أنشئ مجلد HDFS
docker exec -it hadoop /opt/hadoop-3.3.0/bin/hdfs dfs -mkdir -p /traffic-data

# 6. شغّل جميع معالجات NiFi من واجهة NiFi
# افتح https://localhost:8443/nifi
# Username: admin / Password: adminadminadmin
# اضغط Ctrl+A ثم Start

# 7. انقل الملفات إلى HDFS
docker exec -it hadoop /opt/hadoop-3.3.0/bin/hdfs dfs -put /hdfs-staging/* /traffic-data/

# 8. تحقق من النتائج
docker exec -it hadoop /opt/hadoop-3.3.0/bin/hdfs dfs -ls /traffic-data/ | tail -5
docker exec -it postgres psql -U nifi_user -d nifi_db -c "SELECT COUNT(*) FROM intersections;"
```

### روابط المنافذ

| الخدمة | الرابط | الوصف |
|--------|--------|-------|
| NiFi | https://localhost:8443/nifi | واجهة إدارة التدفق |
| HDFS | http://localhost:9870 | مراقبة نظام الملفات |
| Adminer | http://localhost:8080 | إدارة قاعدة البيانات |

---

## 10. مؤشرات الأداء والمراقبة

### NiFi Bulletin Board

تراقب عبر أيقونة التنبيهات في أعلى يمين واجهة NiFi. الأخطاء المتوقعة:

| الخطأ | تفسيره | الإجراء |
|-------|--------|---------|
| `not.found` في FetchFile | ملف حُذف قبل قراءته | طبيعي، يُهمل |
| `did not have valid JSON` | بيانات متسخة وصلت | طبيعي، يثبت عمل النظام |
| `Connection refused` مؤقت | PostgreSQL تتعافى | Yield Duration يتولى الأمر |

### مؤشرات HDFS

```bash
# عدد الملفات المخزنة
docker exec -it hadoop /opt/hadoop-3.3.0/bin/hdfs dfs -count /traffic-data/

# حجم البيانات
docker exec -it hadoop /opt/hadoop-3.3.0/bin/hdfs dfs -du -h /traffic-data/
```

### مؤشرات PostgreSQL

```sql
-- عدد التقاطعات
SELECT COUNT(*) FROM intersections;

-- آخر تحديث
SELECT MAX(updated_at) FROM intersections;

-- التقاطعات حسب الحالة
SELECT status, COUNT(*) FROM intersections GROUP BY status;
```

---

## 11. خطة التوسع المستقبلية

### تحسينات مقترحة

| التحسين | الوصف | الأولوية |
|---------|-------|----------|
| **Apache Kafka** | إضافة Kafka كطبقة وسيطة بين الحساسات و NiFi لتحمل أفضل | عالية |
| **Parquet Format** | التحويل إلى صيغة Parquet لضغط أفضل وأداء أعلى | متوسطة |
| **Hive Integration** | إنشاء جداول خارجية في Hive للاستعلام عن البيانات | متوسطة |
| **Apache Spark** | تحليلات متقدمة وتعلم آلة للتنبؤ بالازدحام | منخفضة |
| **Grafana Dashboard** | لوحة مراقبة لحظية للمرور | منخفضة |
| **Alerting** | تنبيهات تلقائية عند اكتشاف حوادث أو ازدحام شديد | منخفضة |

---

## 12. الملاحق

### الملحق أ: قائمة المعالجات الكاملة

| # | اسم المعالج | النوع | الوظيفة | المدخلات | المخرجات |
|---|------------|-------|---------|----------|----------|
| 1 | Sensors-Incoming-Data | ListFile | مراقبة الملفات الجديدة | - | success |
| 2 | Fetch-Sensor-Files | FetchFile | قراءة محتوى الملفات | success | success |
| 3 | Split-JSON-Records | SplitRecord | تقسيم الملفات إلى سجلات | success | splits |
| 4 | Extract-JSON-Fields | EvaluateJsonPath | استخراج حقول المرور | splits | matched |
| 5 | Fetch-Intersections-From-DB | QueryDatabaseTable | استخراج تزايدي من PostgreSQL | - | success |
| 6 | Extract-DB-Fields | EvaluateJsonPath | استخراج حقول التقاطعات | success | matched |
| 7 | Traffic-Data-Merge | Funnel | دمج المصدرين | matched ×2 | - |
| 8 | Remove-Duplicates | QueryRecord | إزالة التكرار | - | SQL Query |
| 9 | Clean-Traffic-Data | UpdateRecord | تنظيف القيم الشاذة | SQL Query | success |
| 10 | Store-to-HDFS-Staging | PutFile | حفظ مؤقت | success | success |
| 11 | Move-to-HDFS | ExecuteStreamCommand | نقل إلى HDFS | success | original |

### الملحق ب: عينة بيانات قبل وبعد التنظيف

#### قبل التنظيف:
```json
{
  "event_id": "DUPLICATE_EVENT",
  "intersection_id": "INT-0016",
  "vehicle_type": "motorcycle",
  "vehicle_count": "unknown",
  "avg_speed_kmh": -10.0,
  "congestion_level": null,
  "district": "",
  "lane_id": 2,
  "temperature_c": null,
  "visibility_m": -1.0,
  "accident_flag": null,
  "signal_status": null,
  "event_timestamp": "2026-05-07T23:59:37"
}
```

#### بعد التنظيف:
```json
{
  "event_id": "DUPLICATE_EVENT",
  "intersection_id": "INT-0016",
  "vehicle_type": "motorcycle",
  "vehicle_count": 0,
  "avg_speed_kmh": 0.0,
  "congestion_level": "unknown",
  "district": "Unassigned",
  "lane_id": 2,
  "temperature_c": 25.0,
  "visibility_m": 1000.0,
  "accident_flag": false,
  "signal_status": "unknown",
  "event_timestamp": "2026-05-07T23:59:37"
}
```

### الملحق ج: هيكل مجلدات المشروع

```
nifi-project/
├── docker-compose.yml              # إعدادات Docker
├── Dockerfile                      # بناء صورة Python مخصصة
├── README.md                       # هذا التوثيق
├── data/
│   ├── incoming/                   # ملفات JSON الواردة
│   ├── processed/                  # الملفات بعد القراءة
│   │   └── scripts/
│   │       ├── generate_transactions.py  # محاكي المرور
│   │       └── generate_db.py           # محاكي قاعدة البيانات
├── hdfs-staging/                   # منطقة انتقالية لـ HDFS
└── nifi-extensions/
    ├── postgresql-42.7.3.jar      # JDBC Driver
    └── hadoop-conf/               # إعدادات Hadoop
        ├── core-site.xml
        └── hdfs-site.xml


---

