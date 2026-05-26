
# 🐝 مشروع Apache Hive - SCD Type 2

## 📋 نظرة عامة

هذا المشروع يوضح تطبيق **Slowly Changing Dimension Type 2 (SCD2)** باستخدام **Apache Hive** في بيئة Hadoop معزولة عبر Docker. يغطي المشروع دورة حياة كاملة لإدارة بيانات العملاء مع تتبع التغييرات التاريخية، دون استخدام الجداول المعاملاتية (Transactional Tables) أو عمليات UPDATE/DELETE.

---

## 🏠 البنية

```
┌─────────────────────────────────────────────────────┐
│                   Docker Container                   │
│  ┌─────────────────────────────────────────────────┐ │
│  │              itversity/itvdelab                  │ │
│  │  ┌─────────┐  ┌─────────┐                       │ │
│  │  │  Hadoop │  │  Hive   │                       │ │
│  │  │  3.3.0  │  │  3.1.2  │                       │ │
│  │  └─────────┘  └─────────┘                       │ │
│  └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

---

## 📁 هيكل المشروع

```
hive_project/
│   docker-compose.yml          # إعدادات Docker Compose
│   README.md                   # توثيق المشروع (هذا الملف)
│
├─── data/                      # ملفات CSV المدخلة
│       customer_scd2_mixed.csv # بيانات العملاء الأولية (218 سجل)
│       customer_updated.csv    # بيانات العملاء المحدثة (4372 سجل)
│
└─── screenshots/               # لقطات شاشة المشروع
        hive_01.png ~ hive_11.png
```

---

## 🎯 أهداف التعلم

| # | الهدف | الحالة |
|---|-------|--------|
| 1 | إنشاء جداول داخلية (Managed) وخارجية (External) | ✅ |
| 2 | تحميل البيانات إلى كلا النوعين من الجداول | ✅ |
| 3 | ملاحظة الفرق عند حذف الجدول الداخلي مقابل الخارجي | ✅ |
| 4 | معالجة مشكلة الفاصل داخل عمود العنوان | ✅ |
| 5 | إنشاء بُعد العملاء من النوع SCD Type 2 | ✅ |
| 6 | إدراج سجلات جديدة وتحديث السجلات المتغيرة بدون UPDATE/DELETE | ✅ |
| 7 | إيجاد حل بديل لعدم دعم Hive للعمليات المعاملاتية | ✅ |

---

## 🚀 طريقة التشغيل

### المتطلبات الأساسية

- **Docker** و **Docker Compose** مثبتين
- **WSL** (نظام ويندوز الفرعي للينكس) أو بيئة لينكس أصلية
- **8 جيجابايت** من الذاكرة العشوائية كحد أدنى

### الخطوة 1: تجهيز المجلدات

```bash
mkdir -p ~/hive_project/data
mkdir -p ~/hive_project/screenshots
cd ~/hive_project
```

ضع ملفي البيانات (`customer_scd2_mixed.csv`، `customer_updated.csv`) داخل مجلد `data/`.

### الخطوة 2: إنشاء docker-compose.yml

```yaml
version: '3.8'

services:
  hive:
    image: itversity/itvdelab:latest
    container_name: hive_project
    ports:
      - "10000:10000"
      - "9083:9083"
      - "50070:50070"
      - "8088:8088"
      - "8888:8888"
    volumes:
      - ./data:/data
    stdin_open: true
    tty: true
    command: /bin/bash
```

### الخطوة 3: تشغيل الحاوية

```bash
docker compose up -d
docker exec -it hive_project bash
```

### الخطوة 4: تهيئة الخدمات

```bash
/deploy.sh
```

افتح **طرفية جديدة**، ثم:

```bash
docker exec -it hive_project bash
hive
```

---

## 📊 خطوات التنفيذ

### 1. إنشاء قاعدة البيانات

```sql
CREATE DATABASE IF NOT EXISTS customer_scd;
USE customer_scd;
```

### 2. إنشاء الجداول

```sql
-- جدول داخلي (Managed)
CREATE TABLE customers_internal (
  CustomerID INT, Name STRING, Email STRING,
  Phone_Number STRING, Address STRING, JOIN_Date STRING,
  Start_Date STRING, End_Date STRING, Is_Current INT
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
TBLPROPERTIES ("skip.header.line.count"="1");

-- جدول خارجي (External)
CREATE EXTERNAL TABLE customers_external (
  CustomerID INT, Name STRING, Email STRING,
  Phone_Number STRING, Address STRING, JOIN_Date STRING,
  Start_Date STRING, End_Date STRING, Is_Current INT
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION '/user/hive/warehouse/customer_scd.db/customers_external'
TBLPROPERTIES ("skip.header.line.count"="1");
```

### 3. تحميل البيانات

```sql
-- الجدول الداخلي
LOAD DATA LOCAL INPATH '/data/customer_scd2_mixed.csv' INTO TABLE customers_internal;

-- الجدول الخارجي
!hdfs dfs -put /data/customer_scd2_mixed.csv /user/hive/warehouse/customer_scd.db/customers_external/;
```

### 4. حذف الجداول وملاحظة الفرق

```sql
DROP TABLE customers_internal;
SELECT * FROM customers_internal LIMIT 1;  -- خطأ: Table not found

DROP TABLE customers_external;
!hdfs dfs -ls /user/hive/warehouse/customer_scd.db/customers_external;
-- الملف لا يزال موجودًا! ✅
```

### 5. إنشاء جدول SCD2 النهائي

```sql
CREATE EXTERNAL TABLE customer_scd2_final (
  CustomerID INT, Name STRING, Email STRING,
  Phone_Number STRING, Address STRING, JOIN_Date STRING,
  Start_Date STRING, End_Date STRING, Is_Current INT
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION '/user/hive/warehouse/customer_scd.db/customer_scd2_final'
TBLPROPERTIES ("skip.header.line.count"="1");
```

### 6. تحميل بيانات التحديثات

```sql
CREATE TEMPORARY TABLE updates_stage (
  CustomerID INT, Name STRING, Email STRING,
  Phone_Number STRING, Address STRING, JOIN_Date STRING
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
TBLPROPERTIES ("skip.header.line.count"="1");

LOAD DATA LOCAL INPATH '/data/customer_updated.csv' INTO TABLE updates_stage;
```

### 7. تطبيق SCD Type 2

```sql
INSERT OVERWRITE TABLE customer_scd2_final
SELECT ... FROM (
  -- إغلاق السجلات القديمة التي لها تحديثات
  SELECT ...
  FROM customer_scd2_final existing
  LEFT JOIN updates_stage updates ON existing.CustomerID = updates.CustomerID

  UNION ALL

  -- إدراج السجلات الجديدة من ملف التحديثات
  SELECT ...
  FROM updates_stage updates
) combined;
```

### 8. إصلاح القيم الفارغة

```sql
INSERT OVERWRITE TABLE customer_scd2_final
SELECT ..., CASE WHEN Is_Current IS NULL THEN 1 ELSE Is_Current END AS Is_Current
FROM customer_scd2_final;
```

---

## 📈 النتائج

```
إجمالي السجلات:           4586
السجلات التاريخية:        130 (Is_Current = 0)
السجلات الحالية:           4456 (Is_Current = 1)
```

---

## 🔑 الدروس المستفادة

1. **الجداول الداخلية** تخزن البيانات داخل مستودع Hive؛ حذف الجدول **يحذف البيانات**.
2. **الجداول الخارجية** تشير إلى بيانات في مسار HDFS مخصص؛ حذف الجدول **يبقي البيانات**.
3. **SCD Type 2** يتتبع التاريخ بإضافة صف جديد لكل تغيير، باستخدام أعمدة `Start_Date` و `End_Date` و `Is_Current`.
4. **Hive لا يدعم UPDATE/DELETE** على الجداول غير المعاملاتية، لذا استخدمنا `INSERT OVERWRITE` مع `LEFT JOIN` لمحاكاة SCD2.
5. عمود العنوان كان يحتوي على فواصل داخل علامات تنصيص، وتعالجها Hive بشكل صحيح مع CSV SerDe الافتراضي.

---

## 🛠 التقنيات المستخدمة

| التقنية | الإصدار | الغرض |
|---------|---------|-------|
| Docker | أحدث إصدار | العزل وإنشاء الحاويات |
| Apache Hadoop | 3.3.0 | التخزين الموزع (HDFS) |
| Apache Hive | 3.1.2 | مستودع البيانات وواجهة SQL |
| Derby | مدمجة | قاعدة بيانات Metastore لـ Hive |

---

## 📝 المؤلف

- **الاسم**: وليد العباسي
- **تاريخ المشروع**: مايو 2026
- **المقرر**: هندسة البيانات الضخمة باستخدام Apache Hive

---

## 📜 الرخصة

هذا المشروع أُنشئ لأغراض تعليمية كجزء من متطلبات مقرر البيانات الضخمة.
